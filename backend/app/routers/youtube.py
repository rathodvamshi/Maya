from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional, Tuple
import os
import httpx

from app.config import settings
from app.services import redis_service


router = APIRouter(prefix="/api/youtube", tags=["YouTube"])


def _get_api_key() -> str:
    # Prefer settings, fallback to raw env for flexibility
    return (getattr(settings, "YOUTUBE_API_KEY", None) or os.getenv("YOUTUBE_API_KEY") or "").strip()


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a YouTube Search API item into a consistent shape.

    This version only contains snippet-level fields; statistics (views/likes) are
    enriched later when available from the Videos API.
    """
    vid = ((item.get("id") or {}).get("videoId") or "").strip()
    snip = item.get("snippet") or {}
    thumbs = (snip.get("thumbnails") or {})
    thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
    return {
        "videoId": vid,
        "url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
        "title": snip.get("title") or "",
        "channelTitle": snip.get("channelTitle") or "",
        "channelId": snip.get("channelId") or "",
        "thumbnail": thumb,
        "publishedAt": snip.get("publishedAt") or "",
        "description": snip.get("description") or "",
    }


def _tokenize(text: str) -> List[str]:
    import re as _re
    return [t for t in _re.split(r"[^\w]+", (text or "").lower()) if t]


def _text_relevance(query: str, title: str, description: str = "") -> float:
    from collections import Counter
    import math
    from difflib import SequenceMatcher
    q_tokens = _tokenize(query)
    d_tokens = _tokenize(" ".join([title or "", description or ""]))
    if not q_tokens or not d_tokens:
        return 0.0
    qc = Counter(q_tokens)
    dc = Counter(d_tokens)
    dot = sum(qc[t] * dc.get(t, 0) for t in qc)
    if dot == 0:
        return 0.0
    qn = math.sqrt(sum(v * v for v in qc.values()))
    dn = math.sqrt(sum(v * v for v in dc.values()))
    if qn == 0 or dn == 0:
        return 0.0
    base = max(0.0, min(1.0, dot / (qn * dn)))
    # Light fuzzy bonus for near-exact title match to handle typos
    try:
        ratio = SequenceMatcher(a=(query or "").lower(), b=(title or "").lower()).ratio()
        if ratio >= 0.92:
            base = min(1.0, base + 0.1)
        elif ratio >= 0.85:
            base = min(1.0, base + 0.05)
    except Exception:
        pass
    return base


def _official_channel_score(channel_title: str) -> int:
    ch = (channel_title or "").lower()
    official_channels = {
        "t-series",
        "sony music india",
        "sonymusicindiavevo",
        "zee music company",
        "yrf",
        "tips official",
        "saregama",
        "vevo",
        "aditya music",
        "think music india",
        "lahari music",
        "sun tv",
    }
    if any(name in ch for name in official_channels):
        return 1
    if any(tag in ch for tag in ("official", "vevo", "music")):
        return 1
    return 0


def _recency_bonus(published_at: str) -> float:
    from datetime import datetime, timezone
    if not published_at:
        return 0.0
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days = max(0.0, (now - dt).total_seconds() / 86400.0)
        return max(0.0, 0.1 * (1.0 - min(days / 3650.0, 1.0)))
    except Exception:
        return 0.0


def _rank_results(query: str, items: List[Dict[str, Any]], stats_map: Dict[str, Dict[str, Any]] | None = None) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Weighted ranking combining relevance, official, view count and recency."""
    if not items:
        return items, None

    import math
    max_views = 0
    for it in items:
        try:
            max_views = max(max_views, int(((stats_map or {}).get(it.get("videoId") or "") or {}).get("viewCount") or 0))
        except Exception:
            pass

    def final_score(it: Dict[str, Any]) -> float:
        st = (stats_map or {}).get(it.get("videoId") or "") or {}
        title = it.get("title") or ""
        desc = it.get("description") or ""
        ch = it.get("channelTitle") or ""
        pub = it.get("publishedAt") or ""
        try:
            views = int(st.get("viewCount") or 0)
        except Exception:
            views = 0
        relevance = _text_relevance(query, title, desc)
        official = _official_channel_score(ch)
        view_score = (views / max_views) if max_views > 0 else 0.0
        recency = _recency_bonus(pub)
        return 0.45 * relevance + 0.35 * official + 0.20 * view_score + recency

    ranked = sorted(items, key=final_score, reverse=True)
    top = ranked[0] if ranked else None
    # Attach score for debugging (optional)
    if top is not None:
        top["_score"] = round(final_score(top), 4)
    return ranked, top


@router.get("/search")
async def search_youtube(
    q: str = Query(..., min_length=2, max_length=200),
    max_results: int = Query(5, ge=1, le=10),
    region_code: Optional[str] = Query(None, min_length=2, max_length=2, description="ISO 3166-1 alpha-2 region code"),
):
    api_key = _get_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="YouTube API key not configured")

    # Encourage official and popular results; moderate safe search
    params = {
        "part": "snippet",
        "type": "video",
        "safeSearch": "moderate",
        "maxResults": max_results,
        "q": f"{q} official video",
        "order": "viewCount",
        "key": api_key,
    }
    if region_code:
        params["regionCode"] = region_code

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            # Phase 1: search for candidate videos (snippet only)
            resp = await client.get("https://www.googleapis.com/youtube/v3/search", params=params)
            resp.raise_for_status()
            data = resp.json()

            items: List[Dict[str, Any]] = data.get("items") or []
            normalized = [_normalize_item(i) for i in items if (i.get("id") or {}).get("videoId")]
            if not normalized:
                return {"items": [], "top": None}

            # Phase 2: fetch statistics for ranking (views/likes) using Videos API
            ids = ",".join([n["videoId"] for n in normalized if n.get("videoId")])
            stats_map: Dict[str, Dict[str, Any]] = {}
            if ids:
                v_params = {
                    "part": "statistics,snippet",
                    "id": ids,
                    "key": api_key,
                }
                v_resp = await client.get("https://www.googleapis.com/youtube/v3/videos", params=v_params)
                if v_resp.status_code == 200:
                    v_data = v_resp.json()
                    for v in (v_data.get("items") or []):
                        vid = (v.get("id") or "").strip()
                        stats_map[vid] = (v.get("statistics") or {})
                # Non-fatal if stats call fails; we'll just return snippet-ranked results

            ranked, top = _rank_results(q, normalized, stats_map)
            # Attach stats to each item (if available)
            for it in ranked:
                st = stats_map.get(it.get("videoId") or "") or {}
                if st:
                    it["statistics"] = {
                        "viewCount": st.get("viewCount"),
                        "likeCount": st.get("likeCount"),
                        "commentCount": st.get("commentCount"),
                    }
            # Cache top pick for follow-ups (optional)
            try:
                if top and top.get("videoId"):
                    await redis_service.set_prefetched_data(f"yt:best:{q.strip().lower()}", top, ttl_seconds=12 * 3600)
            except Exception:
                pass
            return {"items": ranked, "top": top}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"YouTube API error: {e}") from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"YouTube API network error: {e}") from e


@router.get("/related")
async def related_videos(
    video_id: str = Query(..., min_length=3, max_length=32, description="Current YouTube videoId"),
    max_results: int = Query(5, ge=1, le=10),
):
    """Return related videos for a given videoId, ranked with the same weighted scheme.

    Useful for implementing a "Next" button in the chat UI.
    """
    api_key = _get_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="YouTube API key not configured")

    params = {
        "part": "snippet",
        "type": "video",
        "relatedToVideoId": video_id,
        "safeSearch": "strict",
        "maxResults": max_results,
        "key": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get("https://www.googleapis.com/youtube/v3/search", params=params)
            resp.raise_for_status()
            data = resp.json()
            items: List[Dict[str, Any]] = data.get("items") or []
            normalized = [_normalize_item(i) for i in items if (i.get("id") or {}).get("videoId")]
            if not normalized:
                return {"items": [], "top": None}

            ids = ",".join([n["videoId"] for n in normalized if n.get("videoId")])
            stats_map: Dict[str, Dict[str, Any]] = {}
            if ids:
                v_params = {"part": "statistics,snippet", "id": ids, "key": api_key}
                v_resp = await client.get("https://www.googleapis.com/youtube/v3/videos", params=v_params)
                if v_resp.status_code == 200:
                    v_data = v_resp.json()
                    for v in (v_data.get("items") or []):
                        vid = (v.get("id") or "").strip()
                        stats_map[vid] = (v.get("statistics") or {})

            # For related, we use the first normalized item's title as a lightweight query proxy
            base_q = normalized[0].get("title") or video_id
            ranked, top = _rank_results(base_q, normalized, stats_map)
            for it in ranked:
                st = stats_map.get(it.get("videoId") or "") or {}
                if st:
                    it["statistics"] = {
                        "viewCount": st.get("viewCount"),
                        "likeCount": st.get("likeCount"),
                        "commentCount": st.get("commentCount"),
                    }
            return {"items": ranked, "top": top}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"YouTube API error: {e}") from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"YouTube API network error: {e}") from e
