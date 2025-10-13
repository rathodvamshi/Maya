from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from bson import ObjectId
from pymongo.collection import Collection

try:
	import bleach  # type: ignore
except Exception:  # pragma: no cover - bleach optional at import time, but recommended
	bleach = None
from app.database import get_sessions_collection
from app.security import get_current_active_user

router = APIRouter(prefix="/api/annotations", tags=["Annotations"])

class HighlightItem(BaseModel):
	id: str
	startOffset: int
	endOffset: int
	color: str
	selectedText: str
	note: Optional[str] = None
	createdAt: Optional[str] = None


class MessageAnnotationsUpdate(BaseModel):
	annotatedHtml: str = Field(..., description="HTML string with <span> wrappers for highlights")
	highlights: List[HighlightItem] = Field(default_factory=list)


ALLOWED_TAGS = [
	"span",
	"strong",
	"em",
	"b",
	"i",
	"u",
	"p",
	"br",
]
ALLOWED_ATTRS = {
	"span": [
		"class",
		"style",
		"data-highlight-id",
		"data-color",
		"data-start",
		"data-end",
		"data-note",
	],
}


def _sanitize_html(html: str) -> str:
	if not html:
		return ""
	if bleach is None:
		# If bleach isn't available, return as-is but strongly recommended to install bleach
		return html
	return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)


@router.patch("/sessions/{session_id}/messages/{message_id}")
def update_message_annotations(
	session_id: str,
	message_id: str,
	body: MessageAnnotationsUpdate,
	current_user: Dict[str, Any] = Depends(get_current_active_user),
	sessions: Collection = Depends(get_sessions_collection),
):
	"""Update highlights/annotated HTML for a specific message in a session.

	Tries ObjectId match first; falls back to string _id in subdocument for legacy records.
	"""
	if not ObjectId.is_valid(session_id):
		raise HTTPException(status_code=400, detail="Invalid session ID")

	clean_html = _sanitize_html(body.annotatedHtml)
	highlights_payload = [h.model_dump() for h in body.highlights]

	sess_oid = ObjectId(session_id)

	# Attempt 1: message _id is ObjectId within array
	try:
		msg_oid = ObjectId(message_id)
	except Exception:
		msg_oid = None

	update = {
		"$set": {
			"messages.$[m].annotatedHtml": clean_html,
			"messages.$[m].highlights": highlights_payload,
		}
	}
	array_filters = [{"m._id": msg_oid}] if msg_oid else [{"m._id": message_id}]

	result = sessions.update_one(
		{"_id": sess_oid, "userId": current_user["_id"]},
		update,
		array_filters=array_filters,
	)

	if result.matched_count == 0 or result.modified_count == 0:
		# Fallback: try alternate type for _id in subdoc
		if msg_oid:
			result = sessions.update_one(
				{"_id": sess_oid, "userId": current_user["_id"]},
				update,
				array_filters=[{"m._id": str(msg_oid)}],
			)
	if result.matched_count == 0:
		raise HTTPException(status_code=404, detail="Session or message not found")

	return {"success": True}


@router.get("/sessions/{session_id}/messages/{message_id}")
def get_message_annotations(
	session_id: str,
	message_id: str,
	current_user: Dict[str, Any] = Depends(get_current_active_user),
	sessions: Collection = Depends(get_sessions_collection),
):
	"""Return a single message (AI or user) from a session including annotations if present."""
	if not ObjectId.is_valid(session_id):
		raise HTTPException(status_code=400, detail="Invalid session ID")

	# Support both string and ObjectId types for userId
	user_id = current_user["_id"]
	user_match = {"$or": [{"userId": user_id}]}
	if isinstance(user_id, str) and ObjectId.is_valid(user_id):
		user_match["$or"].append({"userId": ObjectId(user_id)})

	sess = sessions.find_one({"_id": ObjectId(session_id), **user_match}, {"messages": 1})
	if not sess:
		raise HTTPException(status_code=404, detail="Session not found")

	msgs = sess.get("messages", [])
	found = None
	for m in msgs:
		mid = m.get("_id")
		if isinstance(mid, ObjectId):
			if str(mid) == message_id:
				found = m
				break
		elif isinstance(mid, str) and mid == message_id:
			found = m
			break
	if not found:
		raise HTTPException(status_code=404, detail="Message not found")

	# Normalize id to string for client
	if isinstance(found.get("_id"), ObjectId):
		found["_id"] = str(found["_id"])  # type: ignore[index]
	return found
