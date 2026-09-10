# routes/leave.py
from flask import request, jsonify
from models import db, Worker, LeaveRequest, LeaveType, Holiday, LeaveBalance
from utils.helpers import generate_id
from routes import leave_bp
from datetime import datetime, timedelta
from sqlalchemy import func

@leave_bp.route('/requests', methods=['GET'])
def get_leave_requests():
    """Get leave requests with filters"""
    try:
        worker_id = request.args.get('workerId')
        status = request.args.get('status')
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        
        query = LeaveRequest.query
        
        if worker_id:
            query = query.filter_by(worker_id=worker_id)
        if status:
            query = query.filter_by(status=status)
        if start_date:
            query = query.filter(LeaveRequest.start_date >= start_date)
        if end_date:
            query = query.filter(LeaveRequest.end_date <= end_date)
        
        requests = query.order_by(LeaveRequest.created_at.desc()).all()
        
        result = []
        for req in requests:
            data = req.to_dict()
            worker = Worker.query.get(req.worker_id)
            data['workerName'] = worker.name if worker else 'Unknown'
            data['leaveTypeName'] = req.leave_type.name if req.leave_type else None
            result.append(data)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@leave_bp.route('/requests', methods=['POST'])
def create_leave_request():
    """Create a new leave request"""
    try:
        data = request.json
        
        # Calculate total days
        start = datetime.strptime(data.get('startDate'), '%Y-%m-%d').date()
        end = datetime.strptime(data.get('endDate'), '%Y-%m-%d').date()
        total_days = (end - start).days + 1
        
        leave_request = LeaveRequest(
            id=generate_id(),
            worker_id=data.get('workerId'),
            leave_type_id=data.get('leaveTypeId'),
            start_date=start,
            end_date=end,
            total_days=total_days,
            reason=data.get('reason'),
            status='pending',
            notes=data.get('notes')
        )
        
        db.session.add(leave_request)
        db.session.commit()
        
        return jsonify(leave_request.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@leave_bp.route('/requests/<request_id>/approve', methods=['PUT'])
def approve_leave_request(request_id):
    """Approve a leave request"""
    try:
        leave_request = LeaveRequest.query.get_or_404(request_id)
        data = request.json
        
        leave_request.status = 'approved'
        leave_request.approved_by = data.get('approvedBy')
        leave_request.approved_date = datetime.now().date()
        leave_request.notes = data.get('notes', leave_request.notes)
        
        # Update leave balance
        balance = LeaveBalance.query.filter_by(
            worker_id=leave_request.worker_id,
            leave_type_id=leave_request.leave_type_id,
            year=datetime.now().year
        ).first()
        
        if balance:
            balance.used_days += leave_request.total_days
            balance.remaining_days = balance.total_days - balance.used_days
        
        db.session.commit()
        return jsonify(leave_request.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@leave_bp.route('/requests/<request_id>/reject', methods=['PUT'])
def reject_leave_request(request_id):
    """Reject a leave request"""
    try:
        leave_request = LeaveRequest.query.get_or_404(request_id)
        data = request.json
        
        leave_request.status = 'rejected'
        leave_request.notes = data.get('notes', leave_request.notes)
        
        db.session.commit()
        return jsonify(leave_request.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@leave_bp.route('/types', methods=['GET'])
def get_leave_types():
    """Get all leave types"""
    try:
        types = LeaveType.query.all()
        return jsonify([t.to_dict() for t in types])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@leave_bp.route('/types', methods=['POST'])
def create_leave_type():
    """Create a new leave type"""
    try:
        data = request.json
        
        leave_type = LeaveType(
            id=generate_id(),
            name=data.get('name'),
            code=data.get('code'),
            description=data.get('description'),
            days_allowed=int(data.get('daysAllowed', 0)),
            is_paid=data.get('isPaid', True)
        )
        
        db.session.add(leave_type)
        db.session.commit()
        return jsonify(leave_type.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@leave_bp.route('/balances', methods=['GET'])
def get_leave_balances():
    """Get leave balances for workers"""
    try:
        worker_id = request.args.get('workerId')
        year = int(request.args.get('year', datetime.now().year))
        
        query = LeaveBalance.query.filter_by(year=year)
        if worker_id:
            query = query.filter_by(worker_id=worker_id)
        
        balances = query.all()
        
        result = []
        for balance in balances:
            data = balance.to_dict()
            worker = Worker.query.get(balance.worker_id)
            data['workerName'] = worker.name if worker else 'Unknown'
            data['leaveTypeName'] = balance.leave_type.name if balance.leave_type else None
            result.append(data)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@leave_bp.route('/balances/initialize', methods=['POST'])
def initialize_leave_balances():
    """Initialize leave balances for all workers"""
    try:
        data = request.json
        year = int(data.get('year', datetime.now().year))
        
        workers = Worker.query.all()
        leave_types = LeaveType.query.all()
        
        created = 0
        for worker in workers:
            for leave_type in leave_types:
                existing = LeaveBalance.query.filter_by(
                    worker_id=worker.id,
                    leave_type_id=leave_type.id,
                    year=year
                ).first()
                
                if not existing:
                    balance = LeaveBalance(
                        id=generate_id(),
                        worker_id=worker.id,
                        leave_type_id=leave_type.id,
                        year=year,
                        total_days=leave_type.days_allowed,
                        used_days=0,
                        remaining_days=leave_type.days_allowed
                    )
                    db.session.add(balance)
                    created += 1
        
        db.session.commit()
        return jsonify({
            'message': f'Initialized {created} leave balances',
            'created': created
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@leave_bp.route('/holidays', methods=['GET'])
def get_holidays():
    """Get holidays"""
    try:
        year = request.args.get('year', datetime.now().year)
        
        holidays = Holiday.query.filter(
            db.extract('year', Holiday.date) == year
        ).all()
        
        return jsonify([h.to_dict() for h in holidays])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@leave_bp.route('/holidays', methods=['POST'])
def create_holiday():
    """Create a new holiday"""
    try:
        data = request.json
        
        holiday = Holiday(
            id=generate_id(),
            name=data.get('name'),
            date=datetime.strptime(data.get('date'), '%Y-%m-%d').date(),
            description=data.get('description'),
            is_recurring=data.get('isRecurring', False),
            type=data.get('type', 'public')
        )
        
        db.session.add(holiday)
        db.session.commit()
        return jsonify(holiday.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@leave_bp.route('/stats', methods=['GET'])
def get_leave_stats():
    """Get leave statistics"""
    try:
        year = int(request.args.get('year', datetime.now().year))
        
        # Total requests by status
        total = LeaveRequest.query.filter(
            db.extract('year', LeaveRequest.created_at) == year
        ).count()
        
        pending = LeaveRequest.query.filter_by(status='pending').count()
        approved = LeaveRequest.query.filter_by(status='approved').count()
        rejected = LeaveRequest.query.filter_by(status='rejected').count()
        
        # Total days requested
        total_days = db.session.query(func.sum(LeaveRequest.total_days)).scalar() or 0
        
        # Workers on leave today
        today = datetime.now().date()
        on_leave = LeaveRequest.query.filter(
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today,
            LeaveRequest.status == 'approved'
        ).count()
        
        return jsonify({
            'total': total,
            'pending': pending,
            'approved': approved,
            'rejected': rejected,
            'totalDays': total_days,
            'onLeaveToday': on_leave
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500