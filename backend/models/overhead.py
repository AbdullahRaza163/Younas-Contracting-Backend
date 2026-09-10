from models import db
from datetime import datetime
import json

class OverheadCategory(db.Model):
    __tablename__ = 'overhead_categories'
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), default='company')  # company, site
    is_recurring = db.Column(db.Boolean, default=True)
    default_frequency = db.Column(db.String(20), default='monthly')  # daily, weekly, monthly, yearly
    gl_account = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    monthly_overheads = db.relationship('MonthlyOverhead', backref='category', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'isRecurring': self.is_recurring,
            'defaultFrequency': self.default_frequency,
            'glAccount': self.gl_account,
            'isActive': self.is_active,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @staticmethod
    def get_active_categories():
        return OverheadCategory.query.filter_by(is_active=True).all()


class MonthlyOverhead(db.Model):
    __tablename__ = 'monthly_overhead'
    id = db.Column(db.String(20), primary_key=True)
    month = db.Column(db.String(7), nullable=False)
    category_id = db.Column(db.String(20), db.ForeignKey('overhead_categories.id', ondelete='CASCADE'))
    category_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, default=0.0)
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='CASCADE'), nullable=True)
    site_names = db.Column(db.Text, nullable=True)  # Store site names as JSON string
    sites_count = db.Column(db.Integer, default=1)
    working_days = db.Column(db.Integer, default=26)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        per_site = self.amount / self.sites_count if self.sites_count > 0 else 0
        per_day_per_site = per_site / self.working_days if self.working_days > 0 else 0
        
        # Parse site_names from JSON
        site_names_list = []
        if self.site_names:
            try:
                site_names_list = json.loads(self.site_names)
            except:
                # If not JSON, treat as comma-separated
                site_names_list = [name.strip() for name in self.site_names.split(',') if name.strip()]
        
        # If no site_names stored, generate from site_id or get all sites
        if not site_names_list:
            if self.site_id:
                site = self.site
                if site:
                    site_names_list = [site.name]
            else:
                # Get all active site names
                from models import Site
                all_sites = Site.query.filter_by(active=True).all()
                site_names_list = [s.name for s in all_sites]
                if not site_names_list:
                    site_names_list = ['All Sites']
        
        return {
            'id': self.id,
            'month': self.month,
            'categoryId': self.category_id,
            'categoryName': self.category_name,
            'amount': self.amount,
            'siteId': self.site_id,
            'siteNames': site_names_list,  # Return as list for frontend
            'siteName': ', '.join(site_names_list) if site_names_list else 'All Sites',  # For backward compatibility
            'sitesCount': self.sites_count,
            'workingDays': self.working_days,
            'perSite': per_site,
            'perDayPerSite': per_day_per_site,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_per_day(self):
        """Calculate overhead per day per site"""
        if self.sites_count > 0 and self.working_days > 0:
            return (self.amount / self.sites_count) / self.working_days
        return 0
    
    @staticmethod
    def get_overhead_by_month(month, site_id=None):
        query = MonthlyOverhead.query.filter_by(month=month)
        if site_id:
            query = query.filter(
                (MonthlyOverhead.site_id == site_id) | 
                (MonthlyOverhead.site_id.is_(None))
            )
        else:
            query = query.filter(MonthlyOverhead.site_id.is_(None))
        return query.all()
    
    @staticmethod
    def get_total_monthly_overhead(month, site_id=None):
        overheads = MonthlyOverhead.get_overhead_by_month(month, site_id)
        return sum(o.amount for o in overheads)


class OverheadAllocationHistory(db.Model):
    __tablename__ = 'overhead_allocation_history'
    id = db.Column(db.String(20), primary_key=True)
    month = db.Column(db.String(7), nullable=False)
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='CASCADE'))
    total_overhead = db.Column(db.Float, default=0.0)
    allocated_amount = db.Column(db.Float, default=0.0)
    allocation_method = db.Column(db.String(50), default='equal')  # equal, weighted, custom
    allocated_date = db.Column(db.Date, default=datetime.now().date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'month': self.month,
            'siteId': self.site_id,
            'siteName': self.site.name if self.site else None,
            'totalOverhead': self.total_overhead,
            'allocatedAmount': self.allocated_amount,
            'allocationMethod': self.allocation_method,
            'allocatedDate': self.allocated_date.isoformat() if self.allocated_date else None,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def get_allocations_by_month(month):
        return OverheadAllocationHistory.query.filter_by(month=month).all()