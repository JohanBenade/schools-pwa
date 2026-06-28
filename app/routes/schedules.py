"""
Schedules & Programmes routes - E-05 Phase B (author upload flow).

This file (B-2) provides:
  GET  /schedules/            - thin stub: lists draft + published sources so the
                               upload flow is testable. REPLACED by the reader
                               spine view in Phase C.
  GET  /schedules/upload      - render the Upload Schedule form (author-only)
  POST /schedules/upload      - validate + store the original file, INSERT a
                               schedule_source row as 'draft', redirect to review

The review screen, publish action, and the shared gate-protected file-serve
route are added in B-3 (this file is extended, not rewritten).

Server-side permission: every mutating path checks session['can_post_schedule']
(B-07/B-13 lesson - hiding the button is not security). Files are written to the
Render persistent disk under /var/data/schedule_files/, mirroring the Notice
Board pattern (E-04) so the two converge on one file-serve route in B-3 / when
Notice Board un-parks. Tenant-scoped from day one. ASCII-only.
"""

from flask import Blueprint, render_template, request, redirect, session, send_file, abort
from datetime import datetime, timezone
import os
import re
import uuid
from app.services.db import get_connection
from app.services.extract import extract_rows

schedules_bp = Blueprint('schedules', __name__, url_prefix='/schedules')

TENANT_ID = "MARAGON"

# --- Storage (mirrors Notice Board's /var/data/notice_files pattern) -------
SCHEDULE_ROOT = "/var/data/schedule_files"
IMG_DIR = os.path.join(SCHEDULE_ROOT, "img")
DOC_DIR = os.path.join(SCHEDULE_ROOT, "doc")

# --- Validation constants (identical caps to Notice Board) -----------------
IMAGE_EXTS = {"jpg": "jpg", "jpeg": "jpg", "png": "png", "webp": "webp"}
IMAGE_MAX_BYTES = 5 * 1024 * 1024     # 5 MB
PDF_MAX_BYTES = 10 * 1024 * 1024      # 10 MB

# Magic-byte signatures (read first bytes, never trust the uploaded extension)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPG_MAGIC = b"\xff\xd8\xff"
WEBP_RIFF = b"RIFF"
WEBP_TAG = b"WEBP"
PDF_MAGIC = b"%PDF"


def _can_post():
    """Server-side author guard. True only if the session flag is set."""
    return bool(session.get('can_post_schedule'))


def _sniff_image(head):
    """Return canonical ext if head bytes match a supported image type, else None.
    Validates by magic bytes only - the uploaded filename/extension is never trusted."""
    if head.startswith(PNG_MAGIC):
        return "png"
    if head.startswith(JPG_MAGIC):
        return "jpg"
    if head[0:4] == WEBP_RIFF and head[8:12] == WEBP_TAG:
        return "webp"
    return None


def _load_programmes():
    """The seeded programme list for the dropdown (active only, sorted)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, slug FROM programme "
            "WHERE tenant_id = ? AND is_active = 1 ORDER BY sort_order",
            (TENANT_ID,))
        return [dict(r) for r in cur.fetchall()]


def _render_upload(error=None, form=None):
    """Re-render the Upload form, preserving entered text on error. Size limits
    derive from the byte constants (single source of truth) so labels can never
    drift from what the route enforces."""
    form = form or {}
    return render_template(
        'schedules/upload.html',
        programmes=_load_programmes(),
        error=error,
        image_max_mb=IMAGE_MAX_BYTES // (1024 * 1024),
        pdf_max_mb=PDF_MAX_BYTES // (1024 * 1024),
        title=form.get('title', ''),
        term_label=form.get('term_label', ''),
        notes=form.get('notes', ''),
        programme_id=form.get('programme_id', ''),
    )


@schedules_bp.route('/')
def board():
    """
    PHASE B STUB - replaced by the reader spine view in Phase C.
    Lists every source (draft + published) so the upload flow is testable.
    """
    if not session.get('staff_id'):
        return redirect('/')
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT s.id, s.title, s.status, s.term_label, p.name AS programme_name "
            "FROM schedule_source s JOIN programme p ON s.programme_id = p.id "
            "WHERE s.tenant_id = ? AND s.is_active = 1 "
            "ORDER BY s.posted_at DESC",
            (TENANT_ID,))
        rows = [dict(r) for r in cur.fetchall()]
    can_post = _can_post()
    items = "".join(
        '<li><strong>%s</strong> &middot; %s &middot; <em>%s</em></li>' % (
            _esc(r['title']), _esc(r['programme_name']), _esc(r['status']))
        for r in rows
    ) or "<li>No schedules uploaded yet.</li>"
    new_link = ('<p><a href="/schedules/upload">+ Upload Schedule</a></p>'
                if can_post else '')
    return (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>Schedules - SchoolOps</title></head>"
        "<body style=\"font-family:-apple-system,sans-serif;max-width:500px;"
        "margin:0 auto;padding:20px;\">"
        "<h1 style='font-size:22px;color:#1e293b;'>Schedules &amp; Programmes</h1>"
        "<p style='color:#64748b;font-size:13px;'>(Phase B stub - spine view in Phase C)</p>"
        + new_link +
        "<ul style='line-height:1.8;color:#374151;'>" + items + "</ul>"
        "<p><a href='/'>Home</a></p>"
        "</body></html>"
    )


def _esc(s):
    """Minimal HTML escape for the Phase B stub (Phase C uses templates)."""
    from markupsafe import escape
    return str(escape(s if s is not None else ''))


@schedules_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    """Author-only Upload Schedule form + handler."""
    if not session.get('staff_id'):
        return redirect('/')

    # Server-side permission guard (NOT just hiding the button - B-07/B-13).
    if not _can_post():
        return redirect('/schedules/')

    if request.method == 'GET':
        return _render_upload()

    # ---- POST ----
    form = {
        'title': request.form.get('title', '').strip(),
        'term_label': request.form.get('term_label', '').strip(),
        'notes': request.form.get('notes', '').strip(),
        'programme_id': request.form.get('programme_id', '').strip(),
    }

    # Required fields
    if not form['title']:
        return _render_upload("Title is required.", form)

    # Server-side length caps (client maxlength is advisory only - a crafted
    # POST can exceed it). Caps mirror the form's maxlength attributes so the
    # route is the single enforced source of truth.
    if len(form['title']) > 120:
        return _render_upload("Title is too long (max 120 characters).", form)
    if len(form['term_label']) > 60:
        return _render_upload("Term label is too long (max 60 characters).", form)
    if len(form['notes']) > 2000:
        return _render_upload("Notes are too long (max 2000 characters).", form)

    valid_ids = {p['id'] for p in _load_programmes()}
    if form['programme_id'] not in valid_ids:
        return _render_upload("Please choose a valid programme.", form)

    # File: required for a schedule source (the original artifact IS the point).
    # An image OR a PDF. Mirrors Notice Board validation exactly.
    upload_file = request.files.get('file')
    if not upload_file or not upload_file.filename:
        return _render_upload("Please attach the schedule file (image or PDF).", form)

    raw = upload_file.read()
    if len(raw) == 0:
        return _render_upload("The uploaded file is empty.", form)

    file_kind = None       # 'image' | 'pdf'
    canon_ext = None
    if raw[:4] == PDF_MAGIC:
        if len(raw) > PDF_MAX_BYTES:
            return _render_upload("PDF is too large (max 10 MB).", form)
        file_kind = 'pdf'
        canon_ext = 'pdf'
    else:
        canon_ext = _sniff_image(raw[:16])
        if canon_ext is None:
            return _render_upload(
                "File must be a PDF, or a JPG/PNG/WEBP image.", form)
        if len(raw) > IMAGE_MAX_BYTES:
            return _render_upload("Image is too large (max 5 MB).", form)
        file_kind = 'image'

    # ---- Write the original file (UUID name, never trust uploaded name) ----
    # Store the BARE filename in file_path; B-3's serve route joins it back onto
    # IMG_DIR / DOC_DIR. Keeps the DB decoupled from the mount location.
    # abs_path is retained so the file can be removed if the INSERT below fails
    # (no orphaned file left on disk).
    if file_kind == 'image':
        os.makedirs(IMG_DIR, exist_ok=True)
        fname = "%s.%s" % (uuid.uuid4().hex, canon_ext)
        abs_path = os.path.join(IMG_DIR, fname)
    else:
        os.makedirs(DOC_DIR, exist_ok=True)
        fname = "%s.pdf" % uuid.uuid4().hex
        abs_path = os.path.join(DOC_DIR, fname)
    with open(abs_path, 'wb') as f:
        f.write(raw)

    # ---- INSERT schedule_source as draft (tenant-scoped) ----
    source_id = str(uuid.uuid4())
    uploaded_by_id = session.get('staff_id')
    posted_at = datetime.now(timezone.utc).isoformat()
    term_label = form['term_label'] if form['term_label'] else None
    notes = form['notes'] if form['notes'] else None

    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO schedule_source "
                "(id, tenant_id, programme_id, title, term_label, file_path, "
                " file_type, uploaded_by_id, status, posted_at, published_at, "
                " is_active, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, NULL, 1, ?)",
                (source_id, TENANT_ID, form['programme_id'], form['title'],
                 term_label, fname, file_kind, uploaded_by_id, posted_at, notes))
            conn.commit()
        except Exception:
            # INSERT failed: remove the file just written so no orphan is left
            # on disk (the file is only ever served via a DB row, so an
            # unreferenced file would otherwise sit forever). Re-raise after.
            try:
                os.remove(abs_path)
            except OSError:
                pass
            raise

    # ---- E-05 Phase 2: in-app vision extraction (Assessment Timetable) ----
    # The draft + file are now safely persisted. Extraction is a pure
    # ENHANCEMENT layered on top: on ANY failure we do nothing extra and the
    # author lands on the review screen with the empty paste box (the B-3
    # path stays as the permanent safety net). The returned TSV is NOT
    # trusted - it runs through the SAME _parse_rows a human paste does, so a
    # model misread is rejected identically to a bad hand-paste (Model B:
    # never auto-publish; these rows land as an unpublished draft for review).
    prog_slug = next(
        (p['slug'] for p in _load_programmes()
         if p['id'] == form['programme_id']), None)
    if prog_slug == 'assessment-timetable':
        tsv, _err = extract_rows(raw, file_kind, prog_slug)
        if tsv:
            rows, parse_err = _parse_rows(tsv)
            if not parse_err and rows:
                try:
                    with get_connection() as conn:
                        cur = conn.cursor()
                        for r in rows:
                            cur.execute(
                                "INSERT INTO schedule_item "
                                "(id, tenant_id, source_id, programme_id, "
                                " item_date, end_date, start_time, end_time, "
                                " grade, session, venue, label, sub_label, "
                                " sort_hint, is_active) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                                (str(uuid.uuid4()), TENANT_ID, source_id,
                                 form['programme_id'], r['item_date'],
                                 r['end_date'], r['start_time'], r['end_time'],
                                 r['grade'], r['session'], r['venue'],
                                 r['label'], r['sub_label'], r['sort_hint']))
                        conn.commit()
                except Exception:
                    # Extraction is best-effort: a DB hiccup here must not
                    # break the upload. Swallow and fall back to empty paste.
                    pass

    # B-3 switches this redirect to the review screen (see below).
    return redirect('/schedules/review/' + source_id)


# ===========================================================================
# B-3: review screen, paste->items (atomic replace), publish, file-serve.
# All mutating routes are server-side guarded by _can_post(). The file-serve
# route is read-only (everyone past the gate) and built shared-friendly so the
# Notice Board (E-04) reuses it when un-parked.
# ===========================================================================

# Locked 10-column TSV paste contract (handover B-3). programme_id is NOT in the
# paste - it is fixed by the source row. Order is binding:
ITEM_COLS = (
    "item_date", "label", "end_date", "start_time", "end_time",
    "grade", "session", "venue", "sub_label", "sort_hint",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")

# Extension -> MIME for the serve route (only the types the upload route admits).
_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "pdf": "application/pdf",
}


def _load_source(source_id):
    """Fetch one schedule_source (tenant-scoped, active) + its programme name.
    Returns a dict or None. Used by every B-3 route."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT s.id, s.tenant_id, s.programme_id, s.title, s.term_label, "
            "       s.file_path, s.file_type, s.status, s.posted_at, "
            "       s.published_at, s.notes, p.name AS programme_name "
            "FROM schedule_source s JOIN programme p ON s.programme_id = p.id "
            "WHERE s.id = ? AND s.tenant_id = ? AND s.is_active = 1",
            (source_id, TENANT_ID))
        row = cur.fetchone()
        return dict(row) if row else None


def _load_items(source_id):
    """All active draft/published items for a source, date+sort ordered."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, item_date, end_date, start_time, end_time, grade, "
            "       session, venue, label, sub_label, sort_hint "
            "FROM schedule_item "
            "WHERE source_id = ? AND tenant_id = ? AND is_active = 1 "
            "ORDER BY item_date, sort_hint, label",
            (source_id, TENANT_ID))
        return [dict(r) for r in cur.fetchall()]


def _parse_rows(raw_text):
    """Parse the TSV paste into validated row dicts.

    Returns (rows, error). On any invalid row, returns ([], "line N: ...") so the
    caller commits NOTHING (Model B: a misread date must never reach a live spine).
    - Splits on newlines; blank lines skipped.
    - A header line whose first cell is exactly 'item_date' is skipped.
    - Error 'line N' refers to the PHYSICAL line in the pasted text (blank
      and header lines counted), so the user can locate it in the textarea.
    - Each line split on TAB, padded/truncated to the 10-column contract.
    - item_date + label required; dates YYYY-MM-DD; times HH:MM; sort_hint int.
    - Empty optional cells become None.
    """
    rows = []
    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    seen_dataline = 0
    for idx, line in enumerate(lines, start=1):
        if line.strip() == "":
            continue
        cells = line.split("\t")
        # Skip a header line if present (first cell literally 'item_date').
        if cells[0].strip() == "item_date":
            continue
        seen_dataline += 1
        # Normalise to exactly 10 cells.
        cells = (cells + [""] * len(ITEM_COLS))[:len(ITEM_COLS)]
        vals = {col: cells[i].strip() for i, col in enumerate(ITEM_COLS)}

        # Required: item_date + label.
        if not vals["item_date"]:
            return [], "line %d: item_date is required" % idx
        if not _DATE_RE.match(vals["item_date"]):
            return [], "line %d: item_date must be YYYY-MM-DD" % idx
        if not vals["label"]:
            return [], "line %d: label is required" % idx

        # Optional date/time format checks (only if present).
        if vals["end_date"] and not _DATE_RE.match(vals["end_date"]):
            return [], "line %d: end_date must be YYYY-MM-DD" % idx
        if vals["start_time"] and not _TIME_RE.match(vals["start_time"]):
            return [], "line %d: start_time must be HH:MM" % idx
        if vals["end_time"] and not _TIME_RE.match(vals["end_time"]):
            return [], "line %d: end_time must be HH:MM" % idx

        # sort_hint: blank -> 0; else must be an integer.
        sh = vals["sort_hint"]
        if sh == "":
            sort_hint = 0
        else:
            try:
                sort_hint = int(sh)
            except ValueError:
                return [], "line %d: sort_hint must be a whole number" % idx

        rows.append({
            "item_date": vals["item_date"],
            "end_date": vals["end_date"] or None,
            "start_time": vals["start_time"] or None,
            "end_time": vals["end_time"] or None,
            "grade": vals["grade"] or None,
            "session": vals["session"] or None,
            "venue": vals["venue"] or None,
            "label": vals["label"],
            "sub_label": vals["sub_label"] or None,
            "sort_hint": sort_hint,
        })

    if seen_dataline == 0:
        return [], "No data rows found (paste is empty or header-only)."
    return rows, None


def _render_review(source, error=None, notice=None):
    """Render the review screen for a source (always re-fetch items fresh)."""
    return render_template(
        'schedules/review.html',
        source=source,
        items=_load_items(source['id']),
        error=error,
        notice=notice,
    )


@schedules_bp.route('/review/<source_id>')
def review(source_id):
    """Review screen: original-file link + paste box + current items + publish."""
    if not session.get('staff_id'):
        return redirect('/')
    if not _can_post():
        return redirect('/schedules/')
    source = _load_source(source_id)
    if source is None:
        abort(404)
    return _render_review(source)


@schedules_bp.route('/items/<source_id>', methods=['POST'])
def save_items(source_id):
    """Parse the TSV paste and REPLACE this source's draft items (atomic).

    Decision (handover B-3): re-paste replaces - clear existing, insert fresh.
    Published sources are locked: no silent edits to live data."""
    if not session.get('staff_id'):
        return redirect('/')
    if not _can_post():
        return redirect('/schedules/')
    source = _load_source(source_id)
    if source is None:
        abort(404)
    if source['status'] != 'draft':
        return _render_review(
            source, error="This schedule is already published and cannot be edited.")

    raw_text = request.form.get('rows', '')
    rows, parse_err = _parse_rows(raw_text)
    if parse_err:
        return _render_review(source, error=parse_err)

    # Atomic replace: delete existing items for this source, insert the new set.
    # programme_id is copied from the source (denormalised) - never from paste.
    pid = source['programme_id']
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            # Soft-delete the existing items (consistent with the is_active
            # model used by _load_items + the INSERT below). Draft-only by the
            # guard above; the freshly inserted rows replace them in the view.
            cur.execute(
                "UPDATE schedule_item SET is_active = 0 "
                "WHERE source_id = ? AND tenant_id = ? AND is_active = 1",
                (source_id, TENANT_ID))
            for r in rows:
                cur.execute(
                    "INSERT INTO schedule_item "
                    "(id, tenant_id, source_id, programme_id, item_date, end_date, "
                    " start_time, end_time, grade, session, venue, label, "
                    " sub_label, sort_hint, is_active) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                    (str(uuid.uuid4()), TENANT_ID, source_id, pid,
                     r['item_date'], r['end_date'], r['start_time'], r['end_time'],
                     r['grade'], r['session'], r['venue'], r['label'],
                     r['sub_label'], r['sort_hint']))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return _render_review(
        source, notice="Saved %d item(s). Review, then publish." % len(rows))


@schedules_bp.route('/publish/<source_id>', methods=['POST'])
def publish(source_id):
    """Flip a draft source to published. Blocked if empty or already published."""
    if not session.get('staff_id'):
        return redirect('/')
    if not _can_post():
        return redirect('/schedules/')
    source = _load_source(source_id)
    if source is None:
        abort(404)
    if source['status'] != 'draft':
        return _render_review(source, error="This schedule is already published.")
    if len(_load_items(source_id)) == 0:
        return _render_review(
            source, error="Add at least one item before publishing.")

    published_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE schedule_source SET status = 'published', published_at = ? "
            "WHERE id = ? AND tenant_id = ? AND status = 'draft'",
            (published_at, source_id, TENANT_ID))
        conn.commit()
    return redirect('/schedules/')


@schedules_bp.route('/file/<source_id>/<kind>')
def serve_file(source_id, kind):
    """Stream a source's original file. READ-ONLY: everyone past the gate (this
    is the reader's tap-to-open). Shared-friendly so E-04 reuses this shape.

    Guards: kind in {image,pdf}; file_type must match kind; bare UUID filename
    only (no path separators / traversal); file must exist on disk."""
    if not session.get('staff_id'):
        return redirect('/')
    if kind not in ('image', 'pdf'):
        abort(404)
    source = _load_source(source_id)
    if source is None:
        abort(404)
    if source['file_type'] != kind or not source['file_path']:
        abort(404)

    bare = source['file_path']
    # Defence in depth: the value is a UUID filename by construction, but never
    # trust stored data blindly - reject anything that could escape the dir.
    if '/' in bare or '\\' in bare or '..' in bare:
        abort(404)

    base_dir = IMG_DIR if kind == 'image' else DOC_DIR
    abs_path = os.path.join(base_dir, bare)
    if not os.path.isfile(abs_path):
        abort(404)

    ext = bare.rsplit('.', 1)[-1].lower() if '.' in bare else ''
    mimetype = _MIME.get(ext, 'application/octet-stream')
    return send_file(abs_path, mimetype=mimetype, conditional=True)
