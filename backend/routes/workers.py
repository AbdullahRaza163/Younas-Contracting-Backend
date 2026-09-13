# routes/workers.py
from flask import request, jsonify, Response
from datetime import datetime
import base64
import os

from models import Worker, db
from utils.helpers import generate_id
from routes import workers_bp


# ------------------------------------------------------------------
# Helper: extract picture from request (supports file upload OR base64/URL)
# ------------------------------------------------------------------
def _extract_picture(request_obj):
    """
    Returns a picture string (base64 data URL, plain base64, or URL) or None.
    Accepts:
      - multipart/form-data with a 'picture' file field
      - JSON with 'picture' string (base64 data URL or URL)
    """
    content_type = request_obj.content_type or ''

    # Multipart upload
    if 'multipart/form-data' in content_type:
        file = request_obj.files.get('picture')
        if file and file.filename:
            file_bytes = file.read()
            mime = file.mimetype or 'image/jpeg'
            b64 = base64.b64encode(file_bytes).decode('utf-8')
            return f"data:{mime};base64,{b64}"
        return None

    # JSON body
    data = request_obj.get_json(silent=True) or {}
    picture = data.get('picture')
    if picture is not None:
        return picture  # could be data URL, base64, or URL
    return None


def _get_request_data(request_obj):
    """
    Normalizes request payload for both JSON and multipart/form-data.
    Returns (data_dict, picture_value).
    """
    content_type = request_obj.content_type or ''

    if 'multipart/form-data' in content_type:
        data = request_obj.form.to_dict()
        picture = _extract_picture(request_obj)
    else:
        data = request_obj.get_json(silent=True) or {}
        picture = data.get('picture')  # may be None

    return data, picture


# ------------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------------

@workers_bp.route('', methods=['GET'])
def get_workers():
    """Get all active workers"""
    try:
        workers = Worker.query.filter_by(active=True).order_by(Worker.created_at.desc()).all()
        return jsonify([w.to_dict() for w in workers])
    except Exception as e:
        print(f"Error in get_workers: {str(e)}")
        return jsonify({'error': str(e)}), 500


@workers_bp.route('/all', methods=['GET'])
def get_all_workers():
    """Get all workers including inactive"""
    try:
        workers = Worker.query.order_by(Worker.created_at.desc()).all()
        return jsonify([w.to_dict() for w in workers])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@workers_bp.route('', methods=['POST'])
def create_worker():
    """Create a new worker"""
    try:
        data, picture = _get_request_data(request)

        join_date = None
        if data.get('joinDate'):
            join_date = datetime.strptime(data.get('joinDate'), '%Y-%m-%d').date()

        worker = Worker(
            id=generate_id(),
            name=data.get('name'),
            role=data.get('role', ''),
            daily_rate=float(data.get('dailyRate', 0) or 0),
            hourly_rate=float(data.get('hourlyRate', 0) or 0),
            phone=data.get('phone', ''),
            cpr=data.get('cpr', ''),
            join_date=join_date,
            picture=picture,          # <-- NEW
            active=True
        )
        db.session.add(worker)
        db.session.commit()
        return jsonify(worker.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@workers_bp.route('/<worker_id>', methods=['GET'])
def get_worker(worker_id):
    """Get a specific worker"""
    try:
        worker = Worker.query.get_or_404(worker_id)
        return jsonify(worker.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@workers_bp.route('/<worker_id>', methods=['PUT'])
def update_worker(worker_id):
    """Update a worker"""
    try:
        worker = Worker.query.get_or_404(worker_id)
        data, picture = _get_request_data(request)

        worker.name = data.get('name', worker.name)
        worker.role = data.get('role', worker.role)
        worker.daily_rate = float(data.get('dailyRate', worker.daily_rate) or 0)
        worker.hourly_rate = float(data.get('hourlyRate', worker.hourly_rate) or 0)
        worker.phone = data.get('phone', worker.phone)
        worker.cpr = data.get('cpr', worker.cpr)

        if data.get('joinDate'):
            worker.join_date = datetime.strptime(data.get('joinDate'), '%Y-%m-%d').date()

        # Update picture only if provided (allows clearing with empty string)
        if picture is not None:
            worker.picture = picture

        # Handle 'active' from form data (strings 'true'/'false')
        if 'active' in data:
            active_val = data.get('active')
            if isinstance(active_val, str):
                worker.active = active_val.lower() in ('true', '1', 'yes')
            else:
                worker.active = bool(active_val)

        db.session.commit()
        return jsonify(worker.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@workers_bp.route('/<worker_id>', methods=['DELETE'])
def delete_worker(worker_id):
    """Soft delete a worker"""
    try:
        worker = Worker.query.get_or_404(worker_id)
        worker.active = False
        db.session.commit()
        return jsonify({'message': 'Worker deactivated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@workers_bp.route('/by-role/<role>', methods=['GET'])
def get_workers_by_role(role):
    """Get workers by role"""
    try:
        workers = Worker.query.filter_by(role=role, active=True).all()
        return jsonify([w.to_dict() for w in workers])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ------------------------------------------------------------------
# NEW: Serve the worker picture as a raw image (optional)
# Useful if you don't want to embed base64 in every worker response.
# ------------------------------------------------------------------
@workers_bp.route('/<worker_id>/picture', methods=['GET'])
def get_worker_picture(worker_id):
    """Serve the worker's profile picture as an image."""
    try:
        worker = Worker.query.get_or_404(worker_id)

        if not worker.picture:
            return jsonify({'error': 'No picture for this worker'}), 404

        pic = worker.picture

        # Case 1: data URL -> "data:image/png;base64,...."
        if pic.startswith('data:'):
            header, encoded = pic.split(',', 1)
            mime = header.split(';')[0].replace('data:', '') or 'image/jpeg'
            return Response(base64.b64decode(encoded), mimetype=mime)

        # Case 2: external URL -> redirect
        if pic.startswith('http://') or pic.startswith('https://'):
            return jsonify({'url': pic})

        # Case 3: plain base64
        try:
            return Response(base64.b64decode(pic), mimetype='image/jpeg')
        except Exception:
            return jsonify({'error': 'Invalid picture data'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500