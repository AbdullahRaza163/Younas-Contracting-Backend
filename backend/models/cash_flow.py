# models/cash_flow.py
from models import db
from datetime import datetime

class CashFlow(db.Model):
    __tablename__ = 'cash_flows'
    
    id = db.Column(db.String(20), primary_key=True)
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='CASCADE'))
    date = db.Column(db.Date, nullable=False)
    inflow = db.Column(db.Float, default=0.0)
    outflow = db.Column(db.Float, default=0.0)
    net_flow = db.Column(db.Float, default=0.0)
    cumulative_balance = db.Column(db.Float, default=0.0)
    type = db.Column(db.String(20), default='operational')
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = db.relationship('Project', backref='cash_flows')
    
    def to_dict(self):
        return {
            'id': self.id,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'date': self.date.isoformat() if self.date else None,
            'inflow': self.inflow,
            'outflow': self.outflow,
            'netFlow': self.net_flow,
            'cumulativeBalance': self.cumulative_balance,
            'type': self.type,
            'description': self.description,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_net_flow(self):
        self.net_flow = self.inflow - self.outflow
        return self.net_flow
    
    @staticmethod
    def get_by_project(project_id):
        return CashFlow.query.filter_by(project_id=project_id).order_by(CashFlow.date).all()
    
    @staticmethod
    def get_by_date_range(start_date, end_date):
        return CashFlow.query.filter(
            CashFlow.date >= start_date,
            CashFlow.date <= end_date
        ).order_by(CashFlow.date).all()