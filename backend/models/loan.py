# models/loan.py
from models import db
from models.worker import Worker
from datetime import datetime
import random
import string

class LoanType(db.Model):
    __tablename__ = 'loan_types'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    max_amount = db.Column(db.Float, default=0.0)
    interest_rate = db.Column(db.Float, default=0.0)
    default_tenure = db.Column(db.Integer, default=6)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'maxAmount': self.max_amount,
            'interestRate': self.interest_rate,
            'defaultTenure': self.default_tenure,
            'isActive': self.is_active,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class EmployeeLoan(db.Model):
    __tablename__ = 'employee_loans'
    
    id = db.Column(db.String(20), primary_key=True)
    employee_id = db.Column(db.String(20), db.ForeignKey('workers.id', ondelete='CASCADE'), nullable=False)
    loan_type_id = db.Column(db.String(20), db.ForeignKey('loan_types.id', ondelete='SET NULL'))
    loan_number = db.Column(db.String(50), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    remaining_balance = db.Column(db.Float, default=0.0)
    paid_amount = db.Column(db.Float, default=0.0)
    loan_date = db.Column(db.Date, nullable=False)
    tenure_months = db.Column(db.Integer, default=6)
    interest_rate = db.Column(db.Float, default=0.0)
    total_interest = db.Column(db.Float, default=0.0)
    total_payable = db.Column(db.Float, default=0.0)
    monthly_installment = db.Column(db.Float, default=0.0)
    purpose = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')
    approved_by = db.Column(db.String(100))
    approved_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    
    # Auto deduction fields
    auto_deduct = db.Column(db.Boolean, default=False)
    deduction_start_month = db.Column(db.String(7))  # YYYY-MM
    deduction_end_month = db.Column(db.String(7))    # YYYY-MM
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Worker', backref='loans')
    loan_type = db.relationship('LoanType', backref='loans')
    repayments = db.relationship('LoanRepayment', backref='loan', lazy='dynamic', cascade='all, delete-orphan')
    deductions = db.relationship('LoanDeduction', backref='loan', lazy='dynamic', cascade='all, delete-orphan')
    salary_deductions = db.relationship('SalaryDeduction', backref='loan', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        amount = float(self.amount) if self.amount is not None else 0
        remaining_balance = float(self.remaining_balance) if self.remaining_balance is not None else 0
        paid_amount = float(self.paid_amount) if self.paid_amount is not None else 0
        total_payable = float(self.total_payable) if self.total_payable is not None else amount
        monthly_installment = float(self.monthly_installment) if self.monthly_installment is not None else 0
        
        return {
            'id': self.id,
            'employeeId': self.employee_id,
            'employeeName': self.employee.name if self.employee else None,
            'loanTypeId': self.loan_type_id,
            'loanTypeName': self.loan_type.name if self.loan_type else None,
            'loanNumber': self.loan_number,
            'amount': amount,
            'remainingBalance': remaining_balance,
            'paidAmount': paid_amount,
            'loanDate': self.loan_date.isoformat() if self.loan_date else None,
            'tenureMonths': self.tenure_months or 0,
            'interestRate': float(self.interest_rate) if self.interest_rate is not None else 0,
            'totalInterest': float(self.total_interest) if self.total_interest is not None else 0,
            'totalPayable': total_payable,
            'monthlyInstallment': monthly_installment,
            'purpose': self.purpose,
            'status': self.status or 'active',
            'approvedBy': self.approved_by,
            'approvedDate': self.approved_date.isoformat() if self.approved_date else None,
            'notes': self.notes,
            'autoDeduct': self.auto_deduct or False,
            'deductionStartMonth': self.deduction_start_month,
            'deductionEndMonth': self.deduction_end_month,
            'repaymentCount': self.repayments.count(),
            'progress': (paid_amount / total_payable * 100) if total_payable > 0 else 0,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_installment(self):
        """Calculate monthly installment"""
        amount = float(self.amount) if self.amount is not None else 0
        interest_rate = float(self.interest_rate) if self.interest_rate is not None else 0
        tenure_months = int(self.tenure_months) if self.tenure_months is not None else 6
        
        if interest_rate > 0:
            self.total_interest = amount * (interest_rate / 100) * (tenure_months / 12)
            self.total_payable = amount + self.total_interest
            self.monthly_installment = self.total_payable / tenure_months if tenure_months > 0 else self.total_payable
        else:
            self.total_interest = 0
            self.total_payable = amount
            self.monthly_installment = amount / tenure_months if tenure_months > 0 else amount
        
        self.remaining_balance = self.total_payable - (float(self.paid_amount) if self.paid_amount is not None else 0)
        return self.monthly_installment
    
    def update_balance(self):
        """Update remaining balance"""
        total_paid = sum(r.amount for r in self.repayments.all())
        self.paid_amount = total_paid
        self.remaining_balance = (float(self.total_payable) if self.total_payable is not None else 0) - total_paid
        
        if self.remaining_balance <= 0:
            self.status = 'completed'
        
        return self.remaining_balance
    
    @staticmethod
    def generate_loan_number():
        year = datetime.now().year
        count = EmployeeLoan.query.filter(db.extract('year', EmployeeLoan.created_at) == year).count()
        return f"LN-{year}-{str(count + 1).zfill(4)}"
    
    @staticmethod
    def get_by_employee(employee_id):
        return EmployeeLoan.query.filter_by(employee_id=employee_id).all()
    
    @staticmethod
    def get_active_loans():
        return EmployeeLoan.query.filter_by(status='active').all()


class LoanRepayment(db.Model):
    __tablename__ = 'loan_repayments'
    
    id = db.Column(db.String(20), primary_key=True)
    loan_id = db.Column(db.String(20), db.ForeignKey('employee_loans.id', ondelete='CASCADE'), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    principal = db.Column(db.Float, default=0.0)
    interest = db.Column(db.Float, default=0.0)
    payment_method = db.Column(db.String(50), default='cash')
    reference_number = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'loanId': self.loan_id,
            'paymentDate': self.payment_date.isoformat() if self.payment_date else None,
            'amount': float(self.amount) if self.amount is not None else 0,
            'principal': float(self.principal) if self.principal is not None else 0,
            'interest': float(self.interest) if self.interest is not None else 0,
            'paymentMethod': self.payment_method or 'cash',
            'referenceNumber': self.reference_number,
            'notes': self.notes,
            'createdBy': self.created_by,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class LoanDeduction(db.Model):
    __tablename__ = 'loan_deductions'
    
    id = db.Column(db.String(20), primary_key=True)
    loan_id = db.Column(db.String(20), db.ForeignKey('employee_loans.id', ondelete='CASCADE'), nullable=False)
    month = db.Column(db.String(7), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    deducted = db.Column(db.Boolean, default=False)
    deducted_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'loanId': self.loan_id,
            'month': self.month,
            'amount': float(self.amount) if self.amount is not None else 0,
            'deducted': self.deducted or False,
            'deductedDate': self.deducted_date.isoformat() if self.deducted_date else None,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class SalaryDeduction(db.Model):
    __tablename__ = 'salary_deductions'
    
    id = db.Column(db.String(20), primary_key=True)
    employee_id = db.Column(db.String(20), db.ForeignKey('workers.id', ondelete='CASCADE'), nullable=False)
    loan_id = db.Column(db.String(20), db.ForeignKey('employee_loans.id', ondelete='CASCADE'), nullable=False)
    month = db.Column(db.String(7), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    deducted = db.Column(db.Boolean, default=False)
    deducted_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    employee = db.relationship('Worker', backref='salary_deductions')
    
    def to_dict(self):
        return {
            'id': self.id,
            'employeeId': self.employee_id,
            'employeeName': self.employee.name if self.employee else None,
            'loanId': self.loan_id,
            'loanNumber': self.loan.loan_number if self.loan else None,
            'month': self.month,
            'amount': float(self.amount) if self.amount is not None else 0,
            'deducted': self.deducted or False,
            'deductedDate': self.deducted_date.isoformat() if self.deducted_date else None,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }