import random
import string
from datetime import datetime
from models import Invoice, Site, Setting, MonthlyOverhead

def generate_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))

def generate_invoice_number():
    year = datetime.now().year
    count = Invoice.query.filter(
        Invoice.invoice_number.like(f'INV-{year}-%')
    ).count() + 1
    return f"INV-{year}-{str(count).zfill(4)}"

def calculate_daily_overhead(month, site_id=None):
    """Calculate daily overhead for a site based on monthly overhead records"""
    try:
        query = MonthlyOverhead.query.filter_by(month=month)
        
        if site_id:
            query = query.filter(
                (MonthlyOverhead.site_id == site_id) | 
                (MonthlyOverhead.site_id.is_(None))
            )
        else:
            query = query.filter(MonthlyOverhead.site_id.is_(None))
        
        overheads = query.all()
        
        if not overheads:
            setting = Setting.query.filter_by(key='monthly_overhead').first()
            monthly_overhead = float(setting.value) if setting else 194.0
            return monthly_overhead / 30
        
        total_monthly_overhead = sum(o.amount for o in overheads)
        working_days = overheads[0].working_days if overheads else 26
        sites_count = Site.query.filter_by(active=True).count() or 1
        daily_overhead_per_site = (total_monthly_overhead / working_days) / sites_count
        
        return daily_overhead_per_site
        
    except Exception as e:
        print(f"Error calculating overhead: {str(e)}")
        setting = Setting.query.filter_by(key='monthly_overhead').first()
        monthly_overhead = float(setting.value) if setting else 194.0
        return monthly_overhead / 30