# models/site.py
from models import db
from datetime import datetime

class Site(db.Model):
    __tablename__ = 'sites'
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    manager = db.Column(db.String(100))
    manager_salary = db.Column(db.Float, default=0.0)
    phone = db.Column(db.String(20))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - use unique backref names to avoid conflicts
    worker_teams = db.relationship('WorkerTeam', backref='site_ref', lazy='dynamic', cascade='all, delete-orphan')
    expenses = db.relationship('Expense', backref='site', lazy='dynamic', cascade='all, delete-orphan')
    invoices = db.relationship('Invoice', backref='site', lazy='dynamic', cascade='all, delete-orphan')
    monthly_overheads = db.relationship('MonthlyOverhead', backref='site', lazy='dynamic', cascade='all, delete-orphan')
    overhead_allocations = db.relationship('OverheadAllocationHistory', backref='site', lazy='dynamic', cascade='all, delete-orphan')
    daily_entries = db.relationship('DailyEntry', backref='site', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'manager': self.manager,
            'managerSalary': self.manager_salary,
            'phone': self.phone,
            'active': self.active,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def to_dict_with_relations(self):
        data = self.to_dict()
        data['workerTeams'] = [t.to_dict() for t in self.worker_teams.all()] if self.worker_teams else []
        data['expenses'] = [e.to_dict() for e in self.expenses.all()] if self.expenses else []
        data['invoices'] = [i.to_dict() for i in self.invoices.all()] if self.invoices else []
        return data
    
    def get_team_count(self):
        """Get the number of teams at this site"""
        return self.worker_teams.count() if self.worker_teams else 0
    
    def get_total_workers(self):
        """Get the total number of workers across all teams at this site"""
        total = 0
        for team in self.worker_teams.all():
            total += team.get_member_count()
        return total
    
    @staticmethod
    def get_active_sites():
        return Site.query.filter_by(active=True).all()
    
    @staticmethod
    def get_site_by_id(site_id):
        return Site.query.get(site_id)
    
    @staticmethod
    def get_sites_with_teams():
        """Get all sites that have at least one team"""
        return Site.query.join(Site.worker_teams).distinct().all()