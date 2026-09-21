# models/overhead.py
from models import db
from datetime import datetime
import json
import random
import string


def _gen_id(length=9):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


# ============================================
# ⭐ FREQUENCY HELPERS — single source of truth
# ============================================
FREQUENCIES = ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')


def _normalize_frequency(freq):
    f = (freq or 'monthly').lower().strip()
    return f if f in FREQUENCIES else 'monthly'


def _weeks_in_working_days(working_days):
    """Round up to the nearest whole week."""
    wd = max(1, int(working_days or 26))
    return max(1, (wd + 6) // 7)      # ceil(wd / 7)


def compute_monthly_total(amount, frequency, working_days=26):
    """
    Given an amount + frequency, compute the equivalent monthly total.

    - daily      → amount is per working day       → amount × working_days
    - weekly     → amount is per week              → amount × ceil(wd / 7)
    - monthly    → amount is already monthly       → amount
    - quarterly  → amount is per quarter           → amount / 3
    - yearly     → amount is per year              → amount / 12

    Never negative.
    """
    amt = max(0.0, float(amount or 0))
    freq = _normalize_frequency(frequency)
    wd = max(1, int(working_days or 26))

    if freq == 'daily':
        return amt * wd
    if freq == 'weekly':
        return amt * _weeks_in_working_days(wd)
    if freq == 'quarterly':
        return amt / 3.0
    if freq == 'yearly':
        return amt / 12.0
    # monthly / unknown
    return amt


class OverheadCategory(db.Model):
    __tablename__ = 'overhead_categories'
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), default='company')
    is_recurring = db.Column(db.Boolean, default=True)
    default_frequency = db.Column(db.String(20), default='monthly')   # daily|weekly|monthly|quarterly|yearly
    default_amount = db.Column(db.Float, default=0.0)
    gl_account = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    monthly_overheads = db.relationship(
        'MonthlyOverhead',
        backref='category',
        lazy=True,
        cascade='all, delete-orphan',
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'isRecurring': self.is_recurring,
            'defaultFrequency': _normalize_frequency(self.default_frequency),
            'defaultAmount': float(self.default_amount or 0),
            'glAccount': self.gl_account,
            'isActive': self.is_active,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
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
    frequency = db.Column(db.String(20), default='monthly')
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='CASCADE'), nullable=True)
    site_names = db.Column(db.Text, nullable=True)
    sites_count = db.Column(db.Integer, default=1)
    working_days = db.Column(db.Integer, default=26)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --------------------------------------------
    # ⭐ FREQUENCY-AWARE CALCULATIONS
    # --------------------------------------------
    def _resolve_frequency(self):
        return _normalize_frequency(self.frequency)

    def get_monthly_total(self):
        """Frequency-aware monthly total (per-site-total across all sites)."""
        return compute_monthly_total(
            self.amount,
            self._resolve_frequency(),
            self.working_days or 26,
        )

    def get_per_site(self):
        """Monthly total ÷ sites count."""
        sites = max(1, int(self.sites_count or 1))
        return self.get_monthly_total() / sites

    def get_per_day_per_site(self):
        """Per-site monthly ÷ working days."""
        wd = max(1, int(self.working_days or 26))
        return self.get_per_site() / wd

    def calculate_per_day(self):
        """Alias — used by helpers elsewhere in the app."""
        return self.get_per_day_per_site()

    def to_dict(self):
        amount = float(self.amount or 0)
        sites_count = max(1, int(self.sites_count or 1))
        working_days = max(1, int(self.working_days or 26))
        freq = self._resolve_frequency()

        monthly_total = compute_monthly_total(amount, freq, working_days)
        per_site = monthly_total / sites_count
        per_day_per_site = per_site / working_days

        # Parse site_names
        site_names_list = []
        if self.site_names:
            try:
                site_names_list = json.loads(self.site_names)
                if not isinstance(site_names_list, list):
                    site_names_list = []
            except Exception:
                site_names_list = [n.strip() for n in self.site_names.split(',') if n.strip()]

        if not site_names_list:
            if self.site_id:
                site = self.site
                if site:
                    site_names_list = [site.name]
            else:
                from models import Site
                all_sites = Site.query.filter_by(active=True).all()
                site_names_list = [s.name for s in all_sites] or ['All Sites']

        return {
            'id': self.id,
            'month': self.month,
            'categoryId': self.category_id,
            'categoryName': self.category_name,
            'amount': amount,
            'frequency': freq,

            # ⭐ Frequency-aware computed fields
            'monthlyTotal': monthly_total,
            'perSite': per_site,
            'perDayPerSite': per_day_per_site,

            'siteId': self.site_id,
            'siteNames': site_names_list,
            'siteName': ', '.join(site_names_list) if site_names_list else 'All Sites',
            'sitesCount': sites_count,
            'workingDays': working_days,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }

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
        """
        ⭐ Now uses frequency-aware monthly total, not raw amount.
        A daily '5.000' entry contributes 130.000 to the monthly total,
        not 5.000.
        """
        overheads = MonthlyOverhead.get_overhead_by_month(month, site_id)
        return sum(o.get_monthly_total() for o in overheads)


class OverheadAllocationHistory(db.Model):
    __tablename__ = 'overhead_allocation_history'
    id = db.Column(db.String(20), primary_key=True)
    month = db.Column(db.String(7), nullable=False)
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='CASCADE'))
    total_overhead = db.Column(db.Float, default=0.0)
    allocated_amount = db.Column(db.Float, default=0.0)
    allocation_method = db.Column(db.String(50), default='equal')
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
            'createdAt': self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def get_allocations_by_month(month):
        return OverheadAllocationHistory.query.filter_by(month=month).all()