# models/budget.py
from models import db
from datetime import datetime
import random
import string

class Budget(db.Model):
    __tablename__ = 'budgets'
    
    id = db.Column(db.String(20), primary_key=True)
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='CASCADE'))
    category = db.Column(db.String(50), default='general')
    amount = db.Column(db.Float, default=0.0)
    actual_amount = db.Column(db.Float, default=0.0)
    variance = db.Column(db.Float, default=0.0)
    month = db.Column(db.String(7))  # YYYY-MM
    year = db.Column(db.Integer)
    status = db.Column(db.String(20), default='active')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = db.relationship('Project', backref='budgets')
    
    def to_dict(self):
        return {
            'id': self.id,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'category': self.category,
            'amount': self.amount,
            'actualAmount': self.actual_amount,
            'variance': self.variance,
            'month': self.month,
            'year': self.year,
            'status': self.status,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_variance(self):
        """Calculate variance between budget and actual"""
        self.variance = self.amount - self.actual_amount
        return self.variance
    
    @staticmethod
    def get_by_project(project_id):
        return Budget.query.filter_by(project_id=project_id).all()
    
    @staticmethod
    def get_by_month(month):
        return Budget.query.filter_by(month=month).all()
    
    @staticmethod
    def get_by_category(category):
        return Budget.query.filter_by(category=category).all()

class BudgetCategory(db.Model):
    __tablename__ = 'budget_categories'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), default='expense')
    color = db.Column(db.String(20))
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'color': self.color,
            'isDefault': self.is_default
        }