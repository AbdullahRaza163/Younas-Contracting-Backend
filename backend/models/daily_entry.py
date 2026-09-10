from models import db
from datetime import datetime

class DailyEntry(db.Model):
    __tablename__ = 'daily_entries'
    id = db.Column(db.String(20), primary_key=True)
    date = db.Column(db.Date, nullable=False)
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='CASCADE'))
    cladding_sqm = db.Column(db.Float, default=0.0)
    floor_sqm = db.Column(db.Float, default=0.0)
    dadu_sqm = db.Column(db.Float, default=0.0)
    skirting_sqm = db.Column(db.Float, default=0.0)
    waterproof_files = db.Column(db.Float, default=0.0)
    grouting_files = db.Column(db.Float, default=0.0)
    mason_hours = db.Column(db.Float, default=0.0)
    helper_hours = db.Column(db.Float, default=0.0)
    manager_present = db.Column(db.Boolean, default=True)
    car_patrol_bd = db.Column(db.Float, default=0.0)
    revenue_bd = db.Column(db.Float, default=0.0)
    labour_bd = db.Column(db.Float, default=0.0)
    net_bd = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'siteId': self.site_id,
            'claddingSqm': self.cladding_sqm,
            'floorSqm': self.floor_sqm,
            'daduSqm': self.dadu_sqm,
            'skirtingSqm': self.skirting_sqm,
            'waterproofFiles': self.waterproof_files,
            'groutingFiles': self.grouting_files,
            'masonHours': self.mason_hours,
            'helperHours': self.helper_hours,
            'managerPresent': self.manager_present,
            'carPatrolBd': self.car_patrol_bd,
            'revenueBd': self.revenue_bd,
            'labourBd': self.labour_bd,
            'netBd': self.net_bd,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_net(self):
        """Calculate net revenue"""
        self.net_bd = self.revenue_bd - self.labour_bd - self.car_patrol_bd
        return self.net_bd
    
    def calculate_revenue(self):
        """Calculate revenue based on work done"""
        # This would need specific rates for each type of work
        # For now, just sum everything
        total_work = (
            self.cladding_sqm + self.floor_sqm + self.dadu_sqm + 
            self.skirting_sqm + self.waterproof_files + self.grouting_files
        )
        # Assuming a rate per unit of work
        return total_work * 10  # Placeholder rate
    
    @staticmethod
    def get_entries_by_site(site_id):
        return DailyEntry.query.filter_by(site_id=site_id).order_by(DailyEntry.date.desc()).all()
    
    @staticmethod
    def get_entries_by_month(month, site_id=None):
        query = DailyEntry.query.filter(DailyEntry.date.like(f'{month}%'))
        if site_id:
            query = query.filter_by(site_id=site_id)
        return query.order_by(DailyEntry.date.asc()).all()