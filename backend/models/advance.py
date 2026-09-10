# models/advance.py
from models import db
from models.worker import Worker
from datetime import datetime
import random
import string

class AdvanceType(db.Model):
    """Types of advances (Salary Advance, Emergency, Equipment, etc.)"""
    __tablename__ = 'advance_types'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    max_amount = db.Column(db.Float, default=0.0)
    default_tenure = db.Column(db.Integer, default=1)  # in months
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'maxAmount': self.max_amount,
            'defaultTenure': self.default_tenure,
            'isActive': self.is_active,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class EmployeeAdvance(db.Model):
    """Employee advance/loan from salary"""
    __tablename__ = 'employee_advances'
    
    id = db.Column(db.String(20), primary_key=True)
    employee_id = db.Column(db.String(20), db.ForeignKey('workers.id', ondelete='CASCADE'), nullable=False)
    advance_type_id = db.Column(db.String(20), db.ForeignKey('advance_types.id', ondelete='SET NULL'))
    
    advance_number = db.Column(db.String(50), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    remaining_balance = db.Column(db.Float, default=0.0)
    paid_amount = db.Column(db.Float, default=0.0)
    
    advance_date = db.Column(db.Date, nullable=False)
    tenure_months = db.Column(db.Integer, default=1)
    reason = db.Column(db.Text)
    
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled
    
    # Auto deduction fields - ALWAYS enabled for advances
    deduction_start_month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    deduction_end_month = db.Column(db.String(7), nullable=False)    # YYYY-MM
    monthly_deduction = db.Column(db.Float, default=0.0)
    
    approved_by = db.Column(db.String(100))
    approved_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Worker', backref='advances')
    advance_type = db.relationship('AdvanceType', backref='advances')
    repayments = db.relationship('AdvanceRepayment', backref='advance', lazy='dynamic', cascade='all, delete-orphan')
    deductions = db.relationship('AdvanceSalaryDeduction', backref='advance', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        amount = float(self.amount) if self.amount is not None else 0
        remaining_balance = float(self.remaining_balance) if self.remaining_balance is not None else 0
        paid_amount = float(self.paid_amount) if self.paid_amount is not None else 0
        monthly_deduction = float(self.monthly_deduction) if self.monthly_deduction is not None else 0
        
        return {
            'id': self.id,
            'employeeId': self.employee_id,
            'employeeName': self.employee.name if self.employee else None,
            'advanceTypeId': self.advance_type_id,
            'advanceTypeName': self.advance_type.name if self.advance_type else None,
            'advanceNumber': self.advance_number,
            'amount': amount,
            'remainingBalance': remaining_balance,
            'paidAmount': paid_amount,
            'advanceDate': self.advance_date.isoformat() if self.advance_date else None,
            'tenureMonths': self.tenure_months or 1,
            'reason': self.reason,
            'status': self.status or 'active',
            'deductionStartMonth': self.deduction_start_month,
            'deductionEndMonth': self.deduction_end_month,
            'monthlyDeduction': monthly_deduction,
            'approvedBy': self.approved_by,
            'approvedDate': self.approved_date.isoformat() if self.approved_date else None,
            'notes': self.notes,
            'repaymentCount': self.repayments.count(),
            'progress': (paid_amount / amount * 100) if amount > 0 else 0,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_deduction(self):
        """Calculate monthly deduction"""
        amount = float(self.amount) if self.amount is not None else 0
        tenure_months = int(self.tenure_months) if self.tenure_months is not None else 1
        
        # No interest for advances
        self.monthly_deduction = amount / tenure_months if tenure_months > 0 else amount
        self.remaining_balance = amount - (float(self.paid_amount) if self.paid_amount is not None else 0)
        return self.monthly_deduction
    
    def update_balance(self):
        """Update remaining balance"""
        total_paid = sum(r.amount for r in self.repayments.all())
        self.paid_amount = total_paid
        self.remaining_balance = (float(self.amount) if self.amount is not None else 0) - total_paid
        
        if self.remaining_balance <= 0:
            self.status = 'completed'
            self.remaining_balance = 0
        
        return self.remaining_balance
    
    @staticmethod
    def generate_advance_number():
        year = datetime.now().year
        count = EmployeeAdvance.query.filter(db.extract('year', EmployeeAdvance.created_at) == year).count()
        return f"ADV-{year}-{str(count + 1).zfill(4)}"
    
    @staticmethod
    def get_by_employee(employee_id):
        return EmployeeAdvance.query.filter_by(employee_id=employee_id).all()
    
    @staticmethod
    def get_active_advances():
        return EmployeeAdvance.query.filter_by(status='active').all()


class AdvanceRepayment(db.Model):
    """Manual repayments for advances"""
    __tablename__ = 'advance_repayments'
    
    id = db.Column(db.String(20), primary_key=True)
    advance_id = db.Column(db.String(20), db.ForeignKey('employee_advances.id', ondelete='CASCADE'), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), default='cash')
    reference_number = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'advanceId': self.advance_id,
            'paymentDate': self.payment_date.isoformat() if self.payment_date else None,
            'amount': float(self.amount) if self.amount is not None else 0,
            'paymentMethod': self.payment_method or 'cash',
            'referenceNumber': self.reference_number,
            'notes': self.notes,
            'createdBy': self.created_by,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class AdvanceSalaryDeduction(db.Model):
    """Salary deductions for advances"""
    __tablename__ = 'advance_salary_deductions'
    
    id = db.Column(db.String(20), primary_key=True)
    advance_id = db.Column(db.String(20), db.ForeignKey('employee_advances.id', ondelete='CASCADE'), nullable=False)
    employee_id = db.Column(db.String(20), db.ForeignKey('workers.id', ondelete='CASCADE'), nullable=False)
    
    month = db.Column(db.String(7), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    deducted = db.Column(db.Boolean, default=False)
    deducted_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Worker', backref='advance_deductions')
    
    def to_dict(self):
        return {
            'id': self.id,
            'advanceId': self.advance_id,
            'employeeId': self.employee_id,
            'employeeName': self.employee.name if self.employee else None,
            'advanceNumber': self.advance.advance_number if self.advance else None,
            'month': self.month,
            'amount': float(self.amount) if self.amount is not None else 0,
            'deducted': self.deducted or False,
            'deductedDate': self.deducted_date.isoformat() if self.deducted_date else None,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }