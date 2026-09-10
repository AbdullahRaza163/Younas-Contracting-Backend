from models import db
from datetime import datetime
import random
import string
class MonthlySummary(db.Model):
    __tablename__ = 'monthly_summary'
    id = db.Column(db.String(20), primary_key=True)
    month = db.Column(db.String(7), nullable=False, unique=True)
    total_revenue = db.Column(db.Float, default=0.0)
    total_labour = db.Column(db.Float, default=0.0)
    car_patrol = db.Column(db.Float, default=0.0)
    monthly_oh = db.Column(db.Float, default=0.0)
    one_time = db.Column(db.Float, default=0.0)
    net_profit = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='❌ NUKSAN')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'month': self.month,
            'totalRevenue': self.total_revenue,
            'totalLabour': self.total_labour,
            'carPatrol': self.car_patrol,
            'monthlyOh': self.monthly_oh,
            'oneTime': self.one_time,
            'netProfit': self.net_profit,
            'status': self.status,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_net_profit(self):
        """Calculate net profit for the month"""
        self.net_profit = (
            self.total_revenue - self.total_labour - 
            self.car_patrol - self.monthly_oh - self.one_time
        )
        return self.net_profit
    
    def update_status(self):
        """Update status based on net profit"""
        if self.net_profit > 0:
            self.status = '✅ FAIDA'
        elif self.net_profit < 0:
            self.status = '❌ NUKSAN'
        else:
            self.status = '⚖️ BARABAR'
        return self.status
    
    @staticmethod
    def get_summary_by_month(month):
        """Get summary for a specific month"""
        return MonthlySummary.query.filter_by(month=month).first()
    
    @staticmethod
    def get_all_summaries():
        """Get all monthly summaries ordered by month"""
        return MonthlySummary.query.order_by(
            MonthlySummary.month.desc()
        ).all()
    
    @staticmethod
    def calculate_from_entries(month):
        """Calculate monthly summary from entries and attendance"""
        from .entry import Entry
        from .attendance import Attendance
        from .expense import Expense
        
        # Get all entries for the month
        entries = Entry.query.filter(Entry.date.like(f'{month}%')).all()
        total_revenue = sum(e.kamai for e in entries)
        total_labour = sum(e.labour for e in entries)
        total_one_time = sum(e.one_time for e in entries)
        
        # Get expenses for the month
        expenses = Expense.query.filter_by(month=month).all()
        car_patrol = sum(e.amount for e in expenses if e.category == 'car_patrol')
        monthly_oh = sum(e.amount for e in expenses if e.category == 'overhead')
        
        # Create or update summary
        summary = MonthlySummary.get_summary_by_month(month)
        if not summary:
            summary = MonthlySummary(
                id=''.join(random.choices(string.ascii_lowercase + string.digits, k=9)),
                month=month
            )
        
        summary.total_revenue = total_revenue
        summary.total_labour = total_labour
        summary.car_patrol = car_patrol
        summary.monthly_oh = monthly_oh
        summary.one_time = total_one_time
        summary.calculate_net_profit()
        summary.update_status()
        
        return summary