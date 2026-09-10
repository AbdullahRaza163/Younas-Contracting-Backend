from flask import request, jsonify
from datetime import datetime
from models import Worker, db
from utils.helpers import generate_id
from routes import workers_bp

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
        data = request.json
        join_date = None
        if data.get('joinDate'):
            join_date = datetime.strptime(data.get('joinDate'), '%Y-%m-%d').date()
        
        worker = Worker(
            id=generate_id(),
            name=data.get('name'),
            role=data.get('role', ''),
            daily_rate=float(data.get('dailyRate', 0)),
            hourly_rate=float(data.get('hourlyRate', 0)),
            phone=data.get('phone', ''),
            cpr=data.get('cpr', ''),
            join_date=join_date,
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
        data = request.json
        
        worker.name = data.get('name', worker.name)
        worker.role = data.get('role', worker.role)
        worker.daily_rate = float(data.get('dailyRate', worker.daily_rate))
        worker.hourly_rate = float(data.get('hourlyRate', worker.hourly_rate))
        worker.phone = data.get('phone', worker.phone)
        worker.cpr = data.get('cpr', worker.cpr)
        
        if data.get('joinDate'):
            worker.join_date = datetime.strptime(data.get('joinDate'), '%Y-%m-%d').date()
        
        worker.active = data.get('active', worker.active)
        
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