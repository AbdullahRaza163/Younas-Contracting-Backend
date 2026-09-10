# models/project.py
from models import db
from datetime import datetime
import random
import string

class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    code = db.Column(db.String(50), unique=True, nullable=False)
    
    # Project Details
    client = db.Column(db.String(200))
    client_contact = db.Column(db.String(100))
    client_phone = db.Column(db.String(20))
    client_email = db.Column(db.String(100))
    
    # Location
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='SET NULL'))
    
    # Financials
    budget = db.Column(db.Float, default=0.0)
    actual_cost = db.Column(db.Float, default=0.0)
    revenue = db.Column(db.Float, default=0.0)
    
    # Timeline
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    actual_end_date = db.Column(db.Date)
    
    # Status
    status = db.Column(db.String(20), default='planning')
    priority = db.Column(db.String(20), default='medium')
    progress = db.Column(db.Float, default=0.0)
    
    # Risk & Health
    risk_level = db.Column(db.String(20), default='low')
    health_status = db.Column(db.String(20), default='on_track')
    
    # Team
    project_manager = db.Column(db.String(100))
    team_lead = db.Column(db.String(100))
    
    # Additional
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    site = db.relationship('Site', backref='projects')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'code': self.code,
            'client': self.client,
            'clientContact': self.client_contact,
            'clientPhone': self.client_phone,
            'clientEmail': self.client_email,
            'siteId': self.site_id,
            'siteName': self.site.name if self.site else None,
            'budget': self.budget,
            'actualCost': self.actual_cost,
            'revenue': self.revenue,
            'profit': self.revenue - self.actual_cost,
            'profitMargin': ((self.revenue - self.actual_cost) / self.revenue * 100) if self.revenue > 0 else 0,
            'startDate': self.start_date.isoformat() if self.start_date else None,
            'endDate': self.end_date.isoformat() if self.end_date else None,
            'actualEndDate': self.actual_end_date.isoformat() if self.actual_end_date else None,
            'status': self.status,
            'priority': self.priority,
            'progress': self.progress,
            'riskLevel': self.risk_level,
            'healthStatus': self.health_status,
            'projectManager': self.project_manager,
            'teamLead': self.team_lead,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_progress(self):
        """Calculate project progress based on entries and budget"""
        from .entry import Entry
        
        # Get all entries for this project
        entries = Entry.query.filter_by(project_id=self.id).all()
        if not entries:
            return 0
        
        # Calculate total work done
        total_kamai = sum(e.kamai or 0 for e in entries)
        total_labour = sum(e.labour or 0 for e in entries)
        total_material = sum(e.material_cost or 0 for e in entries)
        total_equipment = sum(e.equipment_cost or 0 for e in entries)
        
        actual_cost = total_labour + total_material + total_equipment
        self.actual_cost = actual_cost
        
        # Progress based on budget
        if self.budget > 0:
            progress = (actual_cost / self.budget) * 100
            self.progress = min(progress, 100)
        else:
            self.progress = 0
        
        return self.progress
    
    def calculate_financials(self):
        """Calculate financial summary"""
        from .entry import Entry
        
        entries = Entry.query.filter_by(project_id=self.id).all()
        total_revenue = sum(e.kamai or 0 for e in entries)
        total_cost = sum(
            (e.labour or 0) + 
            (e.material_cost or 0) + 
            (e.equipment_cost or 0) + 
            (e.transport_cost or 0) + 
            (e.other_expense or 0)
            for e in entries
        )
        
        self.revenue = total_revenue
        self.actual_cost = total_cost
        return {
            'revenue': total_revenue,
            'cost': total_cost,
            'profit': total_revenue - total_cost,
            'profitMargin': ((total_revenue - total_cost) / total_revenue * 100) if total_revenue > 0 else 0
        }
    
    def update_health_status(self):
        """Update project health status based on various factors"""
        if self.progress >= 100:
            self.health_status = 'completed'
        elif self.progress > 75:
            self.health_status = 'on_track'
        elif self.progress > 50:
            self.health_status = 'at_risk'
        elif self.progress > 25:
            self.health_status = 'behind'
        else:
            self.health_status = 'critical'
        
        # Check if end_date is passed
        if self.end_date and datetime.now().date() > self.end_date:
            if self.progress < 100:
                self.health_status = 'overdue'
        
        # Update status based on progress
        if self.progress >= 100:
            self.status = 'completed'
        elif self.status == 'planning' and self.progress > 0:
            self.status = 'active'
        
        return self.health_status
    
    @staticmethod
    def generate_code():
        """Generate unique project code"""
        year = datetime.now().year
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"PRJ-{year}-{random_str}"
    
    @staticmethod
    def get_by_status(status):
        return Project.query.filter_by(status=status).all()
    
    @staticmethod
    def get_by_priority(priority):
        return Project.query.filter_by(priority=priority).all()
    
    @staticmethod
    def get_active_projects():
        return Project.query.filter(Project.status.in_(['planning', 'active'])).all()
    
    @staticmethod
    def get_completed_projects():
        return Project.query.filter_by(status='completed').all()
    
    @staticmethod
    def get_overdue_projects():
        today = datetime.now().date()
        return Project.query.filter(
            Project.end_date < today,
            Project.status != 'completed'
        ).all()