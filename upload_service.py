"""
services/upload_service.py
Handles file upload validation, saving, and serving for task submissions.
"""
import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'png', 'jpeg', 'jpg'}
MAX_SIZE_BYTES     = 50 * 1024 * 1024   # 50 MB


def allowed_file(filename):
    """True if the file extension is in the allowed set."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_extension(filename):
    """Return lowercase extension without the dot."""
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ''


def save_submission_file(file_storage):
    """
    Validate and save an uploaded FileStorage object.

    Returns a dict:
      {
        'ok': True,
        'stored_name':     'uuid4.ext',         # what's on disk
        'original_name':   'original.pdf',       # shown to users
        'file_size':       123456,               # bytes
        'file_type':       'pdf',
      }
    or:
      { 'ok': False, 'error': 'message' }
    """
    if not file_storage or file_storage.filename == '':
        return {'ok': False, 'error': 'No file selected.'}

    filename = file_storage.filename
    if not allowed_file(filename):
        ext = get_extension(filename) or 'unknown'
        return {
            'ok': False,
            'error': (
                f'File type ".{ext}" is not allowed. '
                f'Accepted types: PDF, DOC, DOCX, PPT, PPTX, PNG, JPEG, JPG.'
            )
        }

    # Check size BEFORE reading the whole file into memory
    file_storage.seek(0, 2)          # seek to end
    size = file_storage.tell()
    file_storage.seek(0)             # rewind

    if size > MAX_SIZE_BYTES:
        mb = size / (1024 * 1024)
        return {
            'ok': False,
            'error': f'File is too large ({mb:.1f} MB). Maximum allowed size is 50 MB.'
        }

    if size == 0:
        return {'ok': False, 'error': 'Uploaded file is empty.'}

    # Generate a UUID filename to avoid collisions / path traversal
    ext          = get_extension(filename)
    stored_name  = f'{uuid.uuid4().hex}.{ext}'
    upload_dir   = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    save_path    = os.path.join(upload_dir, stored_name)
    file_storage.save(save_path)

    return {
        'ok':            True,
        'stored_name':   stored_name,
        'original_name': secure_filename(filename),
        'file_size':     size,
        'file_type':     ext,
    }


def delete_submission_file(stored_name):
    """Delete a previously uploaded file from disk (best-effort)."""
    if not stored_name:
        return
    try:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], stored_name)
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def submission_file_path(stored_name):
    """Full filesystem path to a stored file."""
    return os.path.join(current_app.config['UPLOAD_FOLDER'], stored_name)
