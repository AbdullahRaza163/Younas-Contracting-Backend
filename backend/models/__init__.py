# models/__init__.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize db
db = SQLAlchemy()

# ============================================
# AUTHENTICATION MODELS - Define first
# ============================================
from models.auth import (
    User as UserBase,
    UserSession as UserSessionBase,
    PasswordReset as PasswordResetBase,
    AuthHelper,
    authenticate_token,
    require_role,
    require_admin,
    require_manager,
    generate_id as auth_generate_id
)


# Create model classes bound to db
class User(UserBase, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(20), primary_key=True, default=auth_generate_id)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='user')
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sessions = db.relationship('UserSession', backref='user', lazy=True, cascade='all, delete-orphan')
    password_resets = db.relationship('PasswordReset', backref='user', lazy=True, cascade='all, delete-orphan')


class UserSession(UserSessionBase, db.Model):
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.String(20), primary_key=True, default=auth_generate_id)
    user_id = db.Column(db.String(20), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    refresh_token = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    is_revoked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)


class PasswordReset(PasswordResetBase, db.Model):
    __tablename__ = 'password_resets'
    
    id = db.Column(db.String(20), primary_key=True, default=auth_generate_id)
    user_id = db.Column(db.String(20), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)


# ============================================
# Import all other models
# ============================================
from models.site import Site
from models.worker import Worker
from models.team import WorkerTeam, TeamMember
from models.entry import Entry
from models.attendance import Attendance
from models.expense import Expense
from models.invoice import Invoice
from models.item import Item
from models.setting import Setting
from models.rate_setup import RateSetup
from models.overhead import MonthlyOverhead, OverheadCategory, OverheadAllocationHistory
from models.daily_entry import DailyEntry
from models.cumulative_tracker import CumulativeTracker
from models.monthly_summary import MonthlySummary
from models.project import Project
from models.budget import Budget, BudgetCategory
from models.forecast import Forecast
from models.cash_flow import CashFlow
from models.budget_alert import BudgetAlert
from models.what_if_scenario import WhatIfScenario
from models.client import (
    Client, 
    ClientContact, 
    ClientCommunication, 
    ClientProject, 
    ClientPayment, 
    ClientMeeting, 
    ClientDocument, 
    ClientSatisfaction
)
from models.equipment import (
    Equipment, EquipmentCategory, EquipmentMaintenance, 
    EquipmentAssignment, EquipmentUsage, EquipmentDepreciation
)
from .quality_control import (
    InspectionType,
    InspectionChecklist,
    Inspection,
    InspectionResult,
    Issue,
    CorrectiveAction,
    SafetyIncident,
    InspectionPhoto
)
from .performance import PerformanceKPI, PerformanceMetric, PerformanceRanking
from .leave import LeaveType, LeaveRequest, Holiday, LeaveBalance
from .inventory import (
    MaterialCategory,
    Supplier,
    Material,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement
)
from .loan import LoanType, EmployeeLoan, LoanRepayment, LoanDeduction, SalaryDeduction 
from .advance import (
    AdvanceType, 
    EmployeeAdvance, 
    AdvanceRepayment, 
    AdvanceSalaryDeduction
)
# from models.dashboard import DashboardStats

# ============================================
# Helper Functions
# ============================================

def generate_id():
    """Generate a short ID - uses the auth generate_id function"""
    return auth_generate_id()


# ============================================
# Exports - Include auth models
# ============================================
__all__ = [
    # Database
    'db',
    
    # Core Models
    'Site',
    'Worker', 
    'WorkerTeam',
    'TeamMember',
    'Entry',
    'Attendance',
    'Expense',
    'Invoice',
    'Item',
    'Setting',
    'RateSetup',
    
    # Overhead Models
    'MonthlyOverhead',
    'OverheadCategory',
    'OverheadAllocationHistory',
    
    # Daily/Summary Models
    'DailyEntry',
    'CumulativeTracker',
    'MonthlySummary',
    
    # Project Models
    'Project',
    'Budget',
    'BudgetCategory',
    'Forecast',
    'CashFlow',
    'BudgetAlert',
    'WhatIfScenario',
    
    # Client Models
    'Client',
    'ClientContact',
    'ClientCommunication',
    'ClientProject',
    'ClientPayment',
    'ClientMeeting',
    'ClientDocument',
    'ClientSatisfaction',
    
    # Equipment Models
    'Equipment',
    'EquipmentCategory',
    'EquipmentMaintenance',
    'EquipmentAssignment',
    'EquipmentUsage',
    'EquipmentDepreciation',
    
    # Quality Control Models
    'InspectionType',
    'InspectionChecklist',
    'Inspection',
    'InspectionResult',
    'Issue',
    'CorrectiveAction',
    'SafetyIncident',
    'InspectionPhoto',
    
    # Performance Models
    'PerformanceKPI',
    'PerformanceMetric',
    'PerformanceRanking',
    
    # Leave Models
    'LeaveType',
    'LeaveRequest',
    'Holiday',
    'LeaveBalance',
    
    # Inventory Models
    'MaterialCategory',
    'Supplier',
    'Material',
    'PurchaseOrder',
    'PurchaseOrderItem',
    'StockMovement',
    
    # Loan Models
    'LoanType',
    'EmployeeLoan',
    'LoanRepayment',
    'LoanDeduction',
    'SalaryDeduction',
    
    # Advance Models
    'AdvanceType',
    'EmployeeAdvance',
    'AdvanceRepayment',
    'AdvanceSalaryDeduction',
    
    # ============================================
    # AUTHENTICATION MODELS
    # ============================================
    'User',
    'UserSession',
    'PasswordReset',
    
    # Auth Helpers
    'AuthHelper',
    'authenticate_token',
    'require_role',
    'require_admin',
    'require_manager',
    
    # Utility
    'generate_id',
    # 'DashboardStats',
]


# ============================================
# Initialize Auth Models with db
# ============================================
def init_auth(app):
    """Initialize authentication in Flask app"""
    from flask import jsonify
    
    # Add auth error handlers
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'error': 'Authentication required'}), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': 'Permission denied'}), 403
    
    return app


# ============================================
# Database Migration Helper
# ============================================
def get_all_models():
    """Get list of all model classes for migration"""
    return [
        Site, Worker, WorkerTeam, TeamMember, Entry, Attendance,
        Expense, Invoice, Item, Setting, RateSetup,
        MonthlyOverhead, OverheadCategory, OverheadAllocationHistory,
        DailyEntry, CumulativeTracker, MonthlySummary,
        Project, Budget, BudgetCategory, Forecast, CashFlow, BudgetAlert, WhatIfScenario,
        Client, ClientContact, ClientCommunication, ClientProject,
        ClientPayment, ClientMeeting, ClientDocument, ClientSatisfaction,
        Equipment, EquipmentCategory, EquipmentMaintenance, EquipmentAssignment,
        EquipmentUsage, EquipmentDepreciation,
        InspectionType, InspectionChecklist, Inspection, InspectionResult,
        Issue, CorrectiveAction, SafetyIncident, InspectionPhoto,
        PerformanceKPI, PerformanceMetric, PerformanceRanking,
        LeaveType, LeaveRequest, Holiday, LeaveBalance,
        MaterialCategory, Supplier, Material, PurchaseOrder,
        PurchaseOrderItem, StockMovement,
        LoanType, EmployeeLoan, LoanRepayment, LoanDeduction, SalaryDeduction,
        AdvanceType, EmployeeAdvance, AdvanceRepayment, AdvanceSalaryDeduction,
        # Auth Models
        User, UserSession, PasswordReset
    ]


# ============================================
# Create All Tables Function
# ============================================
def create_tables(app):
    """Create all tables in the database"""
    with app.app_context():
        db.create_all()
        print("✅ All database tables created/verified")


# ============================================
# Database Cleanup Functions
# ============================================
def cleanup_expired_sessions():
    """Clean up expired user sessions"""
    return AuthHelper.cleanup_expired_sessions()


def cleanup_used_reset_tokens():
    """Clean up used password reset tokens"""
    return AuthHelper.cleanup_used_reset_tokens()


def get_auth_stats():
    """Get authentication statistics"""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_sessions = UserSession.query.count()
    active_sessions = UserSession.query.filter_by(is_revoked=False).count()
    
    return {
        'total_users': total_users,
        'active_users': active_users,
        'total_sessions': total_sessions,
        'active_sessions': active_sessions
    }