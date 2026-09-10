# models/what_if_scenario.py
from models import db
from datetime import datetime

class WhatIfScenario(db.Model):
    __tablename__ = 'what_if_scenarios'
    
    id = db.Column(db.String(20), primary_key=True)
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='CASCADE'))
    name = db.Column(db.String(200), nullable=False)
    cost_change = db.Column(db.Float, default=0.0)
    revenue_change = db.Column(db.Float, default=0.0)
    timeline_change = db.Column(db.Float, default=0.0)
    projected_revenue = db.Column(db.Float, default=0.0)
    projected_cost = db.Column(db.Float, default=0.0)
    projected_profit = db.Column(db.Float, default=0.0)
    impact = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    project = db.relationship('Project', backref='scenarios')
    
    def to_dict(self):
        return {
            'id': self.id,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'name': self.name,
            'costChange': self.cost_change,
            'revenueChange': self.revenue_change,
            'timelineChange': self.timeline_change,
            'projectedRevenue': self.projected_revenue,
            'projectedCost': self.projected_cost,
            'projectedProfit': self.projected_profit,
            'impact': self.impact,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }