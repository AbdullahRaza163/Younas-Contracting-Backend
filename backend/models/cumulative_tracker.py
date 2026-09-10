from models import db
from datetime import datetime

class CumulativeTracker(db.Model):
    __tablename__ = 'cumulative_tracker'
    id = db.Column(db.String(20), primary_key=True)
    date = db.Column(db.Date, nullable=False)
    revenue = db.Column(db.Float, default=0.0)
    labour = db.Column(db.Float, default=0.0)
    oh_share = db.Column(db.Float, default=0.0)
    net = db.Column(db.Float, default=0.0)
    cumulative = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='❌ Nuksan')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'revenue': self.revenue,
            'labour': self.labour,
            'ohShare': self.oh_share,
            'net': self.net,
            'cumulative': self.cumulative,
            'status': self.status,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_status(self):
        """Update status based on cumulative value"""
        if self.cumulative > 0:
            self.status = '✅ Faida'
        elif self.cumulative < 0:
            self.status = '❌ Nuksan'
        else:
            self.status = '⚖️ Barabar'
        return self.status
    
    def update_cumulative(self):
        """Update cumulative total (called when new entry added)"""
        # Get the previous entry by date
        previous = CumulativeTracker.query.order_by(
            CumulativeTracker.date.desc()
        ).first()
        
        if previous:
            self.cumulative = previous.cumulative + self.net
        else:
            self.cumulative = self.net
        
        self.calculate_status()
        return self.cumulative
    
    @staticmethod
    def get_tracker_by_month(month):
        """Get all entries for a specific month"""
        return CumulativeTracker.query.filter(
            CumulativeTracker.date.like(f'{month}%')
        ).order_by(CumulativeTracker.date.asc()).all()
    
    @staticmethod
    def get_latest_tracker():
        """Get the latest tracker entry"""
        return CumulativeTracker.query.order_by(
            CumulativeTracker.date.desc()
        ).first()