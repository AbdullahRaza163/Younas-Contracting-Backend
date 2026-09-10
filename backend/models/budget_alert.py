# models/budget_alert.py
from models import db
from datetime import datetime

class BudgetAlert(db.Model):
    __tablename__ = 'budget_alerts'
    
    id = db.Column(db.String(20), primary_key=True)
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='CASCADE'))
    type = db.Column(db.String(20), nullable=False)
    severity = db.Column(db.String(20), default='warning')
    message = db.Column(db.Text, nullable=False)
    threshold = db.Column(db.Float, default=0.0)
    current_value = db.Column(db.Float, default=0.0)
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    project = db.relationship('Project', backref='alerts')
    
    def to_dict(self):
        return {
            'id': self.id,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'type': self.type,
            'severity': self.severity,
            'message': self.message,
            'threshold': self.threshold,
            'currentValue': self.current_value,
            'isResolved': self.is_resolved,
            'resolvedAt': self.resolved_at.isoformat() if self.resolved_at else None,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def get_active_alerts():
        return BudgetAlert.query.filter_by(is_resolved=False).all()
    
    @staticmethod
    def get_by_project(project_id):
        return BudgetAlert.query.filter_by(project_id=project_id).all()