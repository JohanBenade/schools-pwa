"""
Vision extraction service (E-05 Phase 2) - SHARED.

Turns an uploaded schedule artifact (PDF or image) into the locked 10-column
TSV that the review screen's _parse_rows already validates. One programme shape
is supported for now: the Assessment Timetable (Band-1 colour grid). Other
programmes get their own prompt when Phase 2 widens.

Design contract (handover v131 section 5):
  - NO new dependency. Calls the Anthropic REST endpoint directly via `requests`
    (already in requirements.txt; the app already does outbound HTTPS in
    notion.py / push.py). The `anthropic` SDK is deliberately NOT used.
  - Key + model come from the environment, NEVER from code/repo:
        ANTHROPIC_API_KEY  (required; empty -> fail closed)
        EXTRACT_MODEL      (optional; defaults to a Claude string below)
  - FAIL CLOSED. Any problem (no key, non-200, exception, empty body) returns
    (None, reason). The caller falls back to the empty paste box (B-3 path is
    the permanent safety net). Extraction is an enhancement, never a dependency.
  - ONE attempt, timeout=90. No retry in v1 - predictable per-call cost.
  - The returned TSV is NOT trusted: the caller runs it through the same
    _parse_rows a human paste goes through, so a model misread is rejected
    identically to a bad hand-paste.

ASCII-only. Tenant-agnostic (no DB, no session) - pure transform.
"""

import os
import base64

import requests


# --- Anthropic REST shape (verified against current docs, handover 5.2) -----
API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-4-8"
MAX_TOKENS = 8192          # the Assessment Timetable proof run was ~51 rows
REQUEST_TIMEOUT = 90       # seconds; one attempt only

# media_type for each image extension the upload route admits. The upload route
# stores file_kind as 'image'/'pdf'; for an image we still need the precise
# media_type, derived from the stored file extension by the caller is overkill,
# so we sniff the bytes here (same magic checks the upload route already trusts).
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPG_MAGIC = b"\xff\xd8\xff"
_WEBP_RIFF = b"RIFF"
_WEBP_TAG = b"WEBP"


# --- Prompts per programme shape (only Assessment Timetable for now) --------
# This is the EXACT prompt proven against the real Assessment Timetable PDF
# (51 Term-3 rows, all passing production _parse_rows, correctly graded incl.
# the page-2 column shift and the lower-grades-finish-first asymmetry).
_ASSESSMENT_TIMETABLE_PROMPT = (
    "You are extracting a school assessment timetable into structured rows. "
    "The document is a grid of DATE x GRADE -> SUBJECT. Each filled cell is one "
    "assessment: a subject written for one grade on one date.\n"
    "Output ONLY tab-separated rows, one per line, no header, no commentary, no "
    "markdown. Each row has exactly these 10 tab-separated columns in this "
    "order: item_date, label, end_date, start_time, end_time, grade, session, "
    "venue, sub_label, sort_hint.\n"
    "Fill only: item_date (YYYY-MM-DD), label (the subject text exactly as "
    "written), grade (8, 9, 10, 11, or 12 - the column the cell sits under). "
    "Leave the other 7 columns empty (just the tabs). One row per subject-cell. "
    "Skip blank cells. Only include dates in TERM 3. If a date's row has fewer "
    "subjects than grades, map remaining cells left-to-right to the grades that "
    "still have assessments (lower grades finish first). Output nothing but the "
    "rows."
)

# slug -> prompt. Widen here as Phase 2 covers more programmes.
_PROMPTS = {
    "assessment-timetable": _ASSESSMENT_TIMETABLE_PROMPT,
}


def _image_media_type(file_bytes):
    """Return the precise image/* media_type from magic bytes, or None."""
    head = file_bytes[:16]
    if head.startswith(_PNG_MAGIC):
        return "image/png"
    if head.startswith(_JPG_MAGIC):
        return "image/jpeg"
    if head[0:4] == _WEBP_RIFF and head[8:12] == _WEBP_TAG:
        return "image/webp"
    return None


def _build_source_block(file_bytes, file_kind):
    """Build the document(pdf) or image content block, or (None, reason)."""
    b64 = base64.b64encode(file_bytes).decode("ascii")
    if file_kind == "pdf":
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": b64,
            },
        }, None
    if file_kind == "image":
        media_type = _image_media_type(file_bytes)
        if media_type is None:
            return None, "unsupported_image_type"
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64,
            },
        }, None
    return None, "unsupported_file_kind"


def extract_rows(file_bytes, file_kind, programme_slug):
    """Extract structured TSV rows from an uploaded artifact.

    Args:
        file_bytes:     raw bytes of the uploaded file (already validated upstream).
        file_kind:      'pdf' or 'image' (as the upload route classifies it).
        programme_slug: the source programme's slug; selects the prompt shape.

    Returns:
        (tsv_text, None) on success - the model's tab-separated rows, ready to
        run through the existing _parse_rows; or
        (None, reason)   on any failure (fail closed; caller uses empty paste).
    """
    prompt = _PROMPTS.get(programme_slug)
    if prompt is None:
        return None, "no_prompt_for_programme"

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None, "no_key"

    model = os.environ.get("EXTRACT_MODEL", DEFAULT_MODEL)

    source_block, block_err = _build_source_block(file_bytes, file_kind)
    if block_err is not None:
        return None, block_err

    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": [
            {
                "role": "user",
                "content": [
                    source_block,
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    headers = {
        "x-api-key": key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    try:
        resp = requests.post(
            API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    except Exception:
        # Network error, timeout, DNS, etc. Fail closed - never raise into the
        # upload route; the empty paste box is the safety net.
        return None, "request_failed"

    if resp.status_code != 200:
        return None, "http_%d" % resp.status_code

    try:
        data = resp.json()
    except Exception:
        return None, "bad_json"

    # Join every text block (do NOT assume block 0). Non-text blocks ignored.
    blocks = data.get("content", [])
    parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    tsv = "".join(parts).strip()
    if not tsv:
        return None, "empty_extraction"

    return tsv, None
