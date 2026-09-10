# models/forecast.py
from models import db
from datetime import datetime

class Forecast(db.Model):
    __tablename__ = 'forecasts'
    
    id = db.Column(db.String(20), primary_key=True)
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='CASCADE'))
    month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    predicted_revenue = db.Column(db.Float, default=0.0)
    predicted_cost = db.Column(db.Float, default=0.0)
    predicted_profit = db.Column(db.Float, default=0.0)
    confidence_score = db.Column(db.Float, default=0.0)
    actual_revenue = db.Column(db.Float, default=0.0)
    actual_cost = db.Column(db.Float, default=0.0)
    actual_profit = db.Column(db.Float, default=0.0)
    variance_percentage = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = db.relationship('Project', backref='forecasts')
    
    def to_dict(self):
        return {
            'id': self.id,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'month': self.month,
            'predictedRevenue': self.predicted_revenue,
            'predictedCost': self.predicted_cost,
            'predictedProfit': self.predicted_profit,
            'confidenceScore': self.confidence_score,
            'actualRevenue': self.actual_revenue,
            'actualCost': self.actual_cost,
            'actualProfit': self.actual_profit,
            'variancePercentage': self.variance_percentage,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_variance(self):
        """Calculate variance between predicted and actual"""
        if self.predicted_revenue > 0:
            self.variance_percentage = ((self.actual_revenue - self.predicted_revenue) / self.predicted_revenue) * 100
        return self.variance_percentage
    
    @staticmethod
    def get_by_project(project_id):
        return Forecast.query.filter_by(project_id=project_id).order_by(Forecast.month).all()
    
    @staticmethod
    def get_latest_by_project(project_id, limit=6):
        return Forecast.query.filter_by(project_id=project_id).order_by(Forecast.month.desc()).limit(limit).all()