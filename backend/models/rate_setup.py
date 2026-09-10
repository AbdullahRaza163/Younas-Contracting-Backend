from models import db
from datetime import datetime

class RateSetup(db.Model):
    __tablename__ = 'rate_setup'
    id = db.Column(db.String(20), primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50))  # daily, hourly, monthly
    rate_bd = db.Column(db.Float, default=0.0)
    hourly_rate = db.Column(db.Float, default=0.0)
    monthly_salary = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'name': self.name,
            'type': self.type,
            'rateBd': self.rate_bd,
            'hourlyRate': self.hourly_rate,
            'monthlySalary': self.monthly_salary,
            'description': self.description,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_daily_rate(self):
        """Calculate daily rate from monthly salary"""
        if self.monthly_salary > 0:
            return self.monthly_salary / 26  # Assuming 26 working days
        return self.rate_bd
    
    def calculate_hourly_rate_from_monthly(self):
        """Calculate hourly rate from monthly salary"""
        if self.monthly_salary > 0:
            return self.monthly_salary / (26 * 8)  # 26 days * 8 hours
        return self.hourly_rate
    
    @staticmethod
    def get_rates_by_category(category):
        return RateSetup.query.filter_by(category=category).all()
    
    @staticmethod
    def get_rate_by_name(name):
        return RateSetup.query.filter_by(name=name).first()