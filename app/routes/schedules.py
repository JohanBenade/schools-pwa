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

from flask import Blueprint, render_template, request, redirect, session
from datetime import datetime, timezone
import os
import uuid
from app.services.db import get_connection

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

    # B-2 lands on the board stub (which lists the new draft + links to it).
    # B-3 switches this to redirect('/schedules/review/<id>') once the review
    # screen exists.
    return redirect('/schedules/')
