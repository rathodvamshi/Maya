"""Mini Agent internal pipeline (NLU -> Dialogue Management -> NLG).

Goal: Provide a lightweight, easily extensible pipeline for the inline mini agent
without impacting the main agent. The pipeline wraps the existing ai_service
call with structured pre + post steps.

Stages:
 1. NLU: Intent classification & feature extraction
 2. State Assembly: Build conversation state summary
 3. Policy / Dialogue Manager: Decide strategy
 4. NLG Planning: Build model prompt components
 5. Realization: Call underlying LLM (ai_service) with controlled system prompt
 6. Post-process: Minimal safety & formatting normalization

Design Notes:
 - Pure functions where practical for testability
 - All data passed in explicitly; no global state
 - Defensive fallbacks ensure user always gets a response
 - Low coupling: Only dependency outward is ai_service.get_response

Intents (initial):
  - clarify: User wants explanation of snippet content
  - elaborate: Request for deeper detail / expansion
  - summarize_request: User asks for a summary
  - compare: User compares snippet to something else / asks for differences
  - follow_up: Generic follow up question referencing earlier answer
  - unknown: Fallback

Strategies:
  - direct_answer
  - snippet_summary
  - ask_clarification (ask user to refine if ambiguous)
  - compare_outline

Each strategy controls guidance injected into the composed prompt.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
import re
from datetime import datetime

from app.services import ai_service

# ---------------- Data Structures -----------------
@dataclass
class MiniMessage:
    role: str  # 'user' | 'assistant'
    content: str

@dataclass
class PipelineInput:
    snippet_text: Optional[str]
    user_query: str
    recent_messages: List[MiniMessage]
    system_prompt: str
    max_history: int = 6
    agent_type: str = "mini"  # 'mini' | 'main'
    pinecone_context: Optional[str] = None
    neo4j_facts: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None
    user_facts_semantic: Optional[List[str]] = None
    persistent_memories: Optional[List[Dict[str, Any]]] = None
    full_history: Optional[List[Dict[str, Any]]] = None  # for main agent pass-through

@dataclass
class NLUResult:
    intent: str
    confidence: float
    entities: Dict[str, Any]
    needs_disambiguation: bool = False

@dataclass
class PolicyDecision:
    strategy: str
    rationale: str

@dataclass
class NLGPlan:
    prompt: str
    system_override: str
    tags: Dict[str, Any]

@dataclass
class PipelineOutput:
    text: str
    intent: str
    strategy: str
    confidence: float
    tags: Dict[str, Any]
    fallback_used: bool = False

# --------------- NLU -----------------
_INTENT_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("summarize_request", re.compile(r"\b(summarize|summary|tl;?dr)\b", re.I)),
    ("compare", re.compile(r"\b(compare|difference|differs?|vs\.?|versus)\b", re.I)),
    ("clarify", re.compile(r"\b(what does|meaning of|explain|clarif(y|ication))\b", re.I)),
    ("elaborate", re.compile(r"\b(more detail|expand|elaborate|deeper)\b", re.I)),
]

_FOLLOW_UP_CUES = re.compile(r"\b(why|how|what about|and then|next)\b", re.I)

_DEF_INTENT_FALLBACK = "follow_up"


def nlu_analyze(query: str, snippet_text: str, history: List[MiniMessage]) -> NLUResult:
    q = query.strip()
    lowered = q.lower()
    for name, pattern in _INTENT_PATTERNS:
        if pattern.search(q):
            return NLUResult(intent=name, confidence=0.86, entities={}, needs_disambiguation=False)
    if _FOLLOW_UP_CUES.search(q):
        return NLUResult(intent=_DEF_INTENT_FALLBACK, confidence=0.6, entities={})
    # Heuristic: very short question & snippet long -> clarify
    if len(q.split()) <= 5 and len(snippet_text.split()) > 40:
        return NLUResult(intent="clarify", confidence=0.55, entities={})
    # Unknown fallback
    return NLUResult(intent="clarify", confidence=0.4, entities={}, needs_disambiguation=False)

# --------------- State Assembly -----------------

def build_state(recent: List[MiniMessage], limit: int = 6) -> List[MiniMessage]:
    return recent[-limit:]

# --------------- Policy / Dialogue Manager --------------

def decide_policy(nlu: NLUResult, snippet_text: str, query: str) -> PolicyDecision:
    if nlu.intent == "summarize_request":
        return PolicyDecision(strategy="snippet_summary", rationale="User explicitly requested a summary")
    if nlu.intent == "compare":
        return PolicyDecision(strategy="compare_outline", rationale="User wants comparison context")
    if nlu.intent == "elaborate":
        return PolicyDecision(strategy="direct_answer", rationale="Elaboration still answered directly with depth")
    if nlu.intent == "clarify":
        # If snippet appears large and question vague, maybe ask for clarification
        if len(query.split()) < 4 and len(snippet_text.split()) > 80:
            return PolicyDecision(strategy="ask_clarification", rationale="Short vague query over long snippet")
        return PolicyDecision(strategy="direct_answer", rationale="Clarification can be answered directly")
    # fallback
    return PolicyDecision(strategy="direct_answer", rationale="Default direct answer fallback")

# --------------- NLG Planning -----------------

_STRATEGY_GUIDANCE = {
    "direct_answer": "Provide a concise, context-grounded answer based strictly on the snippet; avoid speculation.",
    "snippet_summary": "Produce a tight summary of the snippet first, then briefly address any specific user ask.",
    "ask_clarification": "Politely request clarification of the user's focus while offering 2-3 possible angles.",
    "compare_outline": "Explain what can and cannot be compared from the snippet; if external context is missing, state assumptions explicitly.",
}


def plan_nlg(pi: PipelineInput, nlu: NLUResult, policy: PolicyDecision, state_msgs: List[MiniMessage]) -> NLGPlan:
    guidance = _STRATEGY_GUIDANCE.get(policy.strategy, _STRATEGY_GUIDANCE["direct_answer"])
    history_block_lines = []
    for m in state_msgs:
        content = m.content.replace("\n", " ")[:400]
        history_block_lines.append(f"{m.role}: {content}")
    history_block = "\n".join(history_block_lines) if history_block_lines else "(no recent history)"

    if pi.agent_type == "mini":
        snippet_preview = (pi.snippet_text or "(no snippet)")[:1800]
        prompt = (
            f"SNIPPET:\n{snippet_preview}\n\n"
            f"RECENT EXCHANGES (truncated):\n{history_block}\n\n"
            f"USER QUERY: {pi.user_query}\n\n"
            f"INTENT: {nlu.intent} (confidence {nlu.confidence:.2f})\n"
            f"STRATEGY: {policy.strategy}\n"
            f"GUIDANCE: {guidance}\n\n"
            "Respond now. Keep under ~180 words unless clarification is needed."
        )
        sys_override = (
            pi.system_prompt + "\nYou MUST stay within the snippet context. If information is missing, state that clearly."
        )
    else:  # main agent
        prompt = (
            f"USER MESSAGE: {pi.user_query}\n\n"
            f"INTENT: {nlu.intent} (confidence {nlu.confidence:.2f})\n"
            f"STRATEGY: {policy.strategy}\n"
            f"GUIDANCE: {guidance}\n\n"
            "Respond helpfully. Respect prior conversation and profile context provided separately."
        )
        sys_override = pi.system_prompt or ""

    tags = {
        "intent": nlu.intent,
        "strategy": policy.strategy,
        "confidence": nlu.confidence,
    }
    return NLGPlan(prompt=prompt, system_override=sys_override, tags=tags)

# --------------- Post Processing -----------------
_SANITIZE_RE = re.compile(r"\s+", re.MULTILINE)

def post_process(text: str) -> str:
    t = text.strip()
    t = _SANITIZE_RE.sub(" ", t)
    # Minor guard: prevent the model from asking the user to paste the snippet again
    if "paste" in t.lower() and "snippet" in t.lower():
        t += "\n(Note: The snippet context was already provided.)"
    return t

# --------------- Local Offline Fallback (no external AI) ---------------
_UNAVAILABLE_SENTINEL = "All AI services are currently unavailable"

def _first_sentences(text: str, max_chars: int = 360) -> str:
    if not text:
        return ""
    trimmed = text.strip().replace("\r", " ")
    # Prefer sentence ends. If none, fall back to hard cut.
    for sep in [". ", "! ", "? "]:
        parts = trimmed.split(sep)
        if len(parts) > 1:
            acc = []
            total = 0
            for p in parts:
                if not p:
                    continue
                # re-add separator
                piece = (p + sep).strip()
                if total + len(piece) > max_chars:
                    break
                acc.append(piece)
                total += len(piece)
            if acc:
                return " ".join(acc).strip()
    return (trimmed[: max_chars - 1] + "…") if len(trimmed) > max_chars else trimmed

def _local_offline_answer(pi: "PipelineInput", nlu: "NLUResult", policy: "PolicyDecision") -> str:
    q = (pi.user_query or "").strip()
    snippet = (pi.snippet_text or "").strip()
    header = "Quick take (offline)"
    note = "Note: Generating a lightweight answer locally because AI services are temporarily unavailable."

    if snippet:
        core = _first_sentences(snippet, 420)
        if nlu.intent == "summarize_request":
            body = f"Here's a brief summary based on the provided snippet: {core}"
        elif nlu.intent == "compare":
            body = (
                "From the snippet alone, I can outline what's present versus what might be compared: "
                f"{core} If you share the other item to compare, I can highlight differences explicitly."
            )
        elif nlu.intent == "ask_clarification":
            body = (
                f"The snippet mainly covers: {core} Could you clarify whether you want a high-level overview, "
                "implementation detail, or potential edge cases?"
            )
        else:  # direct_answer or fallback
            body = (
                f"Based on the snippet, here's a concise explanation relevant to your question{(': '+q) if q else ''}: "
                f"{core}"
            )
        tips = "If you need more depth, specify which part of the snippet you'd like to focus on."
        return f"{header}: {body} \n\n{tips} \n\n{note}"
    # No snippet available
    if q:
        return f"{header}: I can't reach the AI right now, but regarding your question — {q} — could you share a bit more detail so I can help more precisely?\n\n{note}"
    return f"{header}: I can't reach the AI right now. Please provide your question or some context, and I'll assist based on what's available.\n\n{note}"

# --------------- Pipeline Orchestrator -----------------
async def run_pipeline(pi: PipelineInput) -> PipelineOutput:
    # NLU
    nlu = nlu_analyze(pi.user_query, pi.snippet_text, pi.recent_messages)
    # State
    state_msgs = build_state(pi.recent_messages, pi.max_history)
    # Policy
    policy = decide_policy(nlu, pi.snippet_text or "", pi.user_query)
    # NLG Planning
    plan = plan_nlg(pi, nlu, policy, state_msgs)
    # Realization
    fallback_used = False
    try:
        if pi.agent_type == "mini":
            text = await ai_service.get_response(
                prompt=plan.prompt,
                history=[],
                state="mini_inline_pipeline",
                pinecone_context=None,
                neo4j_facts=None,
                profile=None,
                user_facts_semantic=None,
                persistent_memories=None,
                system_override=plan.system_override,
            )
            # Detect universal outage banner and synthesize a local response
            if _UNAVAILABLE_SENTINEL.lower() in (text or "").lower():
                fallback_used = True
                text = _local_offline_answer(pi, nlu, policy)
        else:
            text = await ai_service.get_response(
                prompt=plan.prompt,
                history=pi.full_history or [],
                state="general_conversation",
                pinecone_context=pi.pinecone_context,
                neo4j_facts=pi.neo4j_facts,
                profile=pi.profile,
                user_facts_semantic=pi.user_facts_semantic,
                persistent_memories=pi.persistent_memories,
                system_override=plan.system_override or None,
            )
    except Exception as e:  # noqa: BLE001
        # First fallback attempt: simplified direct prompt (remove metadata sections)
        fallback_used = True
        simple_prompt = (
            f"SNIPPET (truncated):\n{(pi.snippet_text or '')[:1200]}\n\nQUESTION: {pi.user_query}\n\n"
            "Answer based ONLY on the provided context. If unsure or missing info, say so clearly."
        )
        try:
            text = await ai_service.get_response(
                prompt=simple_prompt,
                history=pi.full_history if pi.agent_type == "main" else [],
                state="pipeline_fallback1_main" if pi.agent_type == "main" else "mini_inline_pipeline_fallback1",
                pinecone_context=pi.pinecone_context if pi.agent_type == "main" else None,
                neo4j_facts=pi.neo4j_facts if pi.agent_type == "main" else None,
                profile=pi.profile if pi.agent_type == "main" else None,
                user_facts_semantic=pi.user_facts_semantic if pi.agent_type == "main" else None,
                persistent_memories=pi.persistent_memories if pi.agent_type == "main" else None,
                system_override=plan.system_override or None,
            )
            # If fallback still returns outage banner, synthesize locally
            if pi.agent_type == "mini" and _UNAVAILABLE_SENTINEL.lower() in (text or "").lower():
                text = _local_offline_answer(pi, nlu, policy)
        except Exception as e2:  # noqa: BLE001
            # Final emergency fallback string
            text = (
                "I'm having temporary trouble generating a full answer. "
                f"(Errors: primary={str(e)[:80]} | fallback={str(e2)[:80]}). "
                "Please try rephrasing or ask again shortly."
            )
    final = post_process(text)
    return PipelineOutput(
        text=final,
        intent=nlu.intent,
        strategy=policy.strategy,
        confidence=nlu.confidence,
        tags={**plan.tags, "fallback_used": fallback_used},
        fallback_used=fallback_used,
    )

async def run_mini_pipeline(pi: PipelineInput) -> PipelineOutput:  # backwards compatibility
    if pi.agent_type != "mini":
        pi.agent_type = "mini"
    return await run_pipeline(pi)

__all__ = [
    "MiniMessage",
    "PipelineInput",
    "PipelineOutput",
    "run_pipeline",
    "run_mini_pipeline",
]
