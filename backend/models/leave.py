# models/leave.py
from models import db
from datetime import datetime,timedelta  
import random
import string

class LeaveType(db.Model):
    """Leave Types (Annual, Sick, Emergency, etc.)"""
    __tablename__ = 'leave_types'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.Text)
    days_allowed = db.Column(db.Integer, default=0)
    is_paid = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    requests = db.relationship('LeaveRequest', backref='leave_type', lazy='dynamic')
    balances = db.relationship('LeaveBalance', backref='leave_type', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'daysAllowed': self.days_allowed,
            'isPaid': self.is_paid,
            'isActive': self.is_active,
            'requestCount': self.requests.count(),
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def get_by_code(code):
        return LeaveType.query.filter_by(code=code).first()
    
    @staticmethod
    def get_active_types():
        return LeaveType.query.filter_by(is_active=True).all()


class LeaveRequest(db.Model):
    """Leave Requests"""
    __tablename__ = 'leave_requests'
    
    id = db.Column(db.String(20), primary_key=True)
    worker_id = db.Column(db.String(20), db.ForeignKey('workers.id', ondelete='CASCADE'), nullable=False)
    leave_type_id = db.Column(db.String(20), db.ForeignKey('leave_types.id', ondelete='SET NULL'))
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_days = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'approved', 'rejected', 'cancelled'
    approved_by = db.Column(db.String(100))
    approved_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    worker = db.relationship('Worker', backref='leave_requests')
    
    def to_dict(self):
        return {
            'id': self.id,
            'workerId': self.worker_id,
            'workerName': self.worker.name if self.worker else None,
            'leaveTypeId': self.leave_type_id,
            'leaveTypeName': self.leave_type.name if self.leave_type else None,
            'leaveTypeCode': self.leave_type.code if self.leave_type else None,
            'startDate': self.start_date.isoformat() if self.start_date else None,
            'endDate': self.end_date.isoformat() if self.end_date else None,
            'totalDays': self.total_days,
            'reason': self.reason,
            'status': self.status,
            'approvedBy': self.approved_by,
            'approvedDate': self.approved_date.isoformat() if self.approved_date else None,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_days(self):
        """Calculate total days between start and end dates"""
        if self.start_date and self.end_date:
            self.total_days = (self.end_date - self.start_date).days + 1
        return self.total_days
    
    def approve(self, approved_by):
        """Approve the leave request"""
        self.status = 'approved'
        self.approved_by = approved_by
        self.approved_date = datetime.now().date()
        return self
    
    def reject(self, notes=None):
        """Reject the leave request"""
        self.status = 'rejected'
        if notes:
            self.notes = notes
        return self
    
    def cancel(self):
        """Cancel the leave request"""
        self.status = 'cancelled'
        return self
    
    @staticmethod
    def get_pending_requests():
        return LeaveRequest.query.filter_by(status='pending').all()
    
    @staticmethod
    def get_by_worker(worker_id, status=None):
        query = LeaveRequest.query.filter_by(worker_id=worker_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(LeaveRequest.start_date.desc()).all()
    
    @staticmethod
    def get_by_date_range(start_date, end_date, status='approved'):
        return LeaveRequest.query.filter(
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
            LeaveRequest.status == status
        ).all()


class Holiday(db.Model):
    """Holidays (Public, Company, Religious)"""
    __tablename__ = 'holidays'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    is_recurring = db.Column(db.Boolean, default=False)
    type = db.Column(db.String(20), default='public')  # 'public', 'company', 'religious'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'date': self.date.isoformat() if self.date else None,
            'description': self.description,
            'isRecurring': self.is_recurring,
            'type': self.type,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @staticmethod
    def get_by_year(year):
        return Holiday.query.filter(
            db.extract('year', Holiday.date) == year
        ).all()
    
    @staticmethod
    def get_by_month(year, month):
        return Holiday.query.filter(
            db.extract('year', Holiday.date) == year,
            db.extract('month', Holiday.date) == month
        ).all()
    
    @staticmethod
    def get_upcoming(days=30):
        today = datetime.now().date()
        end_date = today + timedelta(days=days)
        return Holiday.query.filter(
            Holiday.date >= today,
            Holiday.date <= end_date
        ).all()


class LeaveBalance(db.Model):
    """Leave Balances per worker per year"""
    __tablename__ = 'leave_balances'
    
    id = db.Column(db.String(20), primary_key=True)
    worker_id = db.Column(db.String(20), db.ForeignKey('workers.id', ondelete='CASCADE'), nullable=False)
    leave_type_id = db.Column(db.String(20), db.ForeignKey('leave_types.id', ondelete='SET NULL'))
    year = db.Column(db.Integer, nullable=False)
    total_days = db.Column(db.Integer, default=0)
    used_days = db.Column(db.Integer, default=0)
    remaining_days = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    worker = db.relationship('Worker', backref='leave_balances')
    
    __table_args__ = (db.UniqueConstraint('worker_id', 'leave_type_id', 'year', name='unique_worker_leave_year'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'workerId': self.worker_id,
            'workerName': self.worker.name if self.worker else None,
            'leaveTypeId': self.leave_type_id,
            'leaveTypeName': self.leave_type.name if self.leave_type else None,
            'year': self.year,
            'totalDays': self.total_days,
            'usedDays': self.used_days,
            'remainingDays': self.remaining_days,
            'utilization': (self.used_days / self.total_days * 100) if self.total_days > 0 else 0,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_remaining(self):
        """Calculate remaining days"""
        self.remaining_days = self.total_days - self.used_days
        return self.remaining_days
    
    def use_days(self, days):
        """Use leave days"""
        if days <= self.remaining_days:
            self.used_days += days
            self.remaining_days = self.total_days - self.used_days
            return True
        return False
    
    @staticmethod
    def get_by_worker(worker_id, year=None):
        if not year:
            year = datetime.now().year
        return LeaveBalance.query.filter_by(worker_id=worker_id, year=year).all()
    
    @staticmethod
    def get_by_leave_type(worker_id, leave_type_id, year=None):
        if not year:
            year = datetime.now().year
        return LeaveBalance.query.filter_by(
            worker_id=worker_id,
            leave_type_id=leave_type_id,
            year=year
        ).first()
    
    @staticmethod
    def initialize_balance(worker_id, leave_type_id, year, total_days):
        """Initialize leave balance for a worker"""
        existing = LeaveBalance.get_by_leave_type(worker_id, leave_type_id, year)
        if existing:
            return existing
        
        balance = LeaveBalance(
            id=''.join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            worker_id=worker_id,
            leave_type_id=leave_type_id,
            year=year,
            total_days=total_days,
            used_days=0,
            remaining_days=total_days
        )
        return balance