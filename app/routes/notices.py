"""
Notice Board routes - E-04 Phase B (author post flow).

Provides:
  GET  /notices/        - thin board stub (REPLACED by the real gallery in Phase C)
  GET  /notices/new     - render the New Notice form (author-only)
  POST /notices/new     - validate + store image (+ optional PDF), INSERT notice row

Server-side permission: every mutating path checks session['can_post_notice'].
Files are written to the Render persistent disk under /var/data/notice_files/.
Tenant-scoped from day one (no S-03 residue debt for this new table).
ASCII-only.
"""

from flask import (Blueprint, render_template, request, redirect,
                   session, send_file, abort)
from markupsafe import escape
from datetime import datetime, timezone
import os
import uuid
from app.services.db import get_connection

notices_bp = Blueprint('notices', __name__, url_prefix='/notices')

TENANT_ID = "MARAGON"

# --- Storage ---------------------------------------------------------------
NOTICE_ROOT = "/var/data/notice_files"
IMG_DIR = os.path.join(NOTICE_ROOT, "img")
DOC_DIR = os.path.join(NOTICE_ROOT, "doc")

# --- Validation constants --------------------------------------------------
CATEGORIES = ["Management", "Sport", "Cultural", "Academic", "Staff", "General"]

IMAGE_EXTS = {"jpg": "jpg", "jpeg": "jpg", "png": "png", "webp": "webp"}
IMAGE_MAX_BYTES = 5 * 1024 * 1024     # 5 MB
PDF_MAX_BYTES = 10 * 1024 * 1024      # 10 MB

# Magic-byte signatures (read first bytes, do NOT trust extension)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPG_MAGIC = b"\xff\xd8\xff"
WEBP_RIFF = b"RIFF"
WEBP_TAG = b"WEBP"
PDF_MAGIC = b"%PDF"

# Mimetypes for the serve route (mirrors schedules.py). Stored filenames
# only ever end in jpg/png/webp/pdf (canonicalised at write time), so this
# map is complete; anything else falls back to octet-stream.
_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "pdf": "application/pdf",
}


def _can_post():
    """Server-side author guard. True only if the session flag is set."""
    return bool(session.get('can_post_notice'))


def _author_desk_for_role(role):
    """
    Derive the display stamp from ROLE (not a hardcoded identity - B-13 lesson).
    principal/deputy -> 'Management'; activities (Delene) -> 'Sport Office'.
    Unknown/missing role -> 'Management' as a safe label, but this should not
    occur: the can_post_notice guard upstream only passes sessions that also
    carry a role (both are set together from the same user_session row).
    """
    if role in ('principal', 'deputy', 'admin'):
        return 'Management'
    if role == 'activities':
        return 'Sport Office'
    # Defensive: a flagged author with an unexpected role still gets a valid,
    # non-misleading label. If this ever fires, the role set needs review.
    return 'Management'


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


def _render_form(error=None, form=None):
    """Re-render the New Notice form, preserving entered text on error.
    Upload size limits are derived from the byte constants (single source of
    truth) and passed to the template so the labels can never drift from
    what the route actually enforces."""
    form = form or {}
    return render_template(
        'notices/new.html',
        categories=CATEGORIES,
        error=error,
        image_max_mb=IMAGE_MAX_BYTES // (1024 * 1024),
        pdf_max_mb=PDF_MAX_BYTES // (1024 * 1024),
        title=form.get('title', ''),
        body=form.get('body', ''),
        category=form.get('category', ''),
        is_pinned=form.get('is_pinned', ''),
        notify=form.get('notify', ''),
    )


# Category -> home-grid gradient class. The six categories map onto the live
# bg-* classes already defined in the home templates, so badges and no-image
# placeholders read as native to the app (not a bolted-on palette).
CATEGORY_BG = {
    "Management": "bg-blue",
    "Sport": "bg-teal",
    "Cultural": "bg-purple",
    "Academic": "bg-amber",
    "Staff": "bg-orange",
    "General": "bg-slate",
}


@notices_bp.route('/')
def board():
    """
    PHASE C reader gallery. Everyone past the gate reads; can-post authors also
    see the New Notice control. Cards render a poster thumbnail (served by
    serve_file below) or a category-coloured placeholder when a notice carries
    no image (image_path is nullable as of schema_version 14). Pinned first,
    then newest first. Tenant-scoped.
    """
    if not session.get('staff_id'):
        return redirect('/')
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, body, category, image_path, attachment_path, "
            "author_desk, posted_at "
            "FROM notice WHERE tenant_id = ? AND is_active = 1 "
            "ORDER BY is_pinned DESC, posted_at DESC",
            (TENANT_ID,))
        rows = [dict(r) for r in cur.fetchall()]
    # Back target = the grid the user tapped the tile from. Management roles
    # tap from the Operations grid (/tools/); every other role taps from their
    # own home (/). Same privileged set the app uses in /tools/ and home().
    role = session.get('role')
    back_url = '/tools/' if role in ('principal', 'deputy', 'management', 'admin') else '/'
    return render_template(
        'notices/board.html',
        rows=rows,
        categories=CATEGORIES,
        category_bg=CATEGORY_BG,
        can_post=_can_post(),
        back_url=back_url,
    )


@notices_bp.route('/file/<notice_id>/<kind>')
def serve_file(notice_id, kind):
    """Stream a notice's image or PDF. READ-ONLY: everyone past the gate (these
    are internal posters/documents). Mirrors schedules.py::serve_file.

    Guards: kind in {image,pdf}; notice must exist (tenant-scoped, active); the
    requested column must be populated; bare UUID filename only (no path
    separators / traversal); file must exist on disk."""
    if not session.get('staff_id'):
        return redirect('/')
    if kind not in ('image', 'pdf'):
        abort(404)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT image_path, attachment_path FROM notice "
            "WHERE id = ? AND tenant_id = ? AND is_active = 1",
            (notice_id, TENANT_ID))
        row = cur.fetchone()
    if row is None:
        abort(404)
    bare = row['image_path'] if kind == 'image' else row['attachment_path']
    if not bare:
        abort(404)
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


@notices_bp.route('/new', methods=['GET', 'POST'])
def new_notice():
    """Author-only New Notice form + handler."""
    if not session.get('staff_id'):
        return redirect('/')

    # Server-side permission guard (NOT just hiding the button - B-07/B-13).
    if not _can_post():
        return redirect('/notices/')

    if request.method == 'GET':
        return _render_form()

    # ---- POST ----
    form = {
        'title': request.form.get('title', '').strip(),
        'body': request.form.get('body', '').strip(),
        'category': request.form.get('category', '').strip(),
        'is_pinned': request.form.get('is_pinned', ''),
        'notify': request.form.get('notify', ''),
    }

    # Required text fields
    if not form['title']:
        return _render_form("Title is required.", form)
    if form['category'] not in CATEGORIES:
        return _render_form("Please choose a valid category.", form)

    # Optional image (Phase C 5.1: image is no longer required).
    # Only read/validate when one is actually uploaded; image_path stays NULL
    # otherwise (schema_version 14 made notice.image_path nullable).
    image = request.files.get('image')
    img_bytes = None
    canon_ext = None
    if image and image.filename:
        img_bytes = image.read()
        if len(img_bytes) == 0:
            return _render_form("The image file is empty.", form)
        if len(img_bytes) > IMAGE_MAX_BYTES:
            return _render_form("Image is too large (max 5 MB).", form)
        canon_ext = _sniff_image(img_bytes[:16])
        if canon_ext is None:
            return _render_form("Image must be a JPG, PNG, or WEBP file.", form)

    # Optional PDF
    doc = request.files.get('attachment')
    doc_bytes = None
    if doc and doc.filename:
        doc_bytes = doc.read()
        if len(doc_bytes) > PDF_MAX_BYTES:
            return _render_form("PDF is too large (max 10 MB).", form)
        if not doc_bytes[:4] == PDF_MAGIC:
            return _render_form("Attachment must be a PDF file.", form)

    # Combined validity guard (Phase C 5.1): a notice needs title + category
    # (checked above) PLUS at least one of {body, image, PDF}. Title+category
    # alone is rejected. This must run AFTER both file inputs are resolved.
    if not form['body'] and img_bytes is None and doc_bytes is None:
        return _render_form(
            "Add at least one of: a body message, an image, or a PDF.", form)

    # ---- Write files (UUID names, never trust uploaded filename) ----
    # Spec 3.3: store the RELATIVE filename in the DB, not the absolute path.
    # Phase C's serve route joins the stored filename back onto IMG_DIR / DOC_DIR.
    # This keeps the DB decoupled from the mount location.
    image_path = None
    if img_bytes is not None:
        os.makedirs(IMG_DIR, exist_ok=True)
        img_name = "%s.%s" % (uuid.uuid4().hex, canon_ext)
        with open(os.path.join(IMG_DIR, img_name), 'wb') as f:
            f.write(img_bytes)
        image_path = img_name  # store bare filename

    attachment_path = None
    attachment_type = None
    if doc_bytes is not None:
        os.makedirs(DOC_DIR, exist_ok=True)
        doc_name = "%s.pdf" % uuid.uuid4().hex
        with open(os.path.join(DOC_DIR, doc_name), 'wb') as f:
            f.write(doc_bytes)
        attachment_path = doc_name  # store bare filename
        attachment_type = 'pdf'

    # ---- INSERT (tenant-scoped) ----
    # NOTE: the 'notify' form toggle is intentionally NOT acted on in Phase B.
    # Push fan-out is Phase E, which reads request.form['notify'] at post time
    # to decide whether to fire. notify_sent stays 0 here (no push sent yet).
    notice_id = str(uuid.uuid4())
    posted_by_id = session.get('staff_id')
    author_desk = _author_desk_for_role(session.get('role'))
    is_pinned = 1 if form['is_pinned'] == '1' else 0
    posted_at = datetime.now(timezone.utc).isoformat()
    body_val = form['body'] if form['body'] else None

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notice "
            "(id, tenant_id, title, body, category, image_path, "
            " attachment_path, attachment_type, posted_by_id, author_desk, "
            " is_pinned, notify_sent, posted_at, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1)",
            (notice_id, TENANT_ID, form['title'], body_val, form['category'],
             image_path, attachment_path, attachment_type, posted_by_id,
             author_desk, is_pinned, posted_at))
        conn.commit()

    # Success -> land on the board (Phase C will show the gallery).
    return redirect('/notices/')
