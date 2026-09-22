# utils/helpers.py
import random
import string
import calendar
import math
from datetime import datetime

from models import Invoice, Site, Setting, MonthlyOverhead


# ============================================
# ID / invoice helpers
# ============================================
def generate_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))


def generate_invoice_number():
    year = datetime.now().year
    count = Invoice.query.filter(
        Invoice.invoice_number.like(f'INV-{year}-%')
    ).count() + 1
    return f"INV-{year}-{str(count).zfill(4)}"


# ============================================
# DAILY OVERHEAD CALCULATION — FREQUENCY-AWARE
# ============================================
def _days_in_month(month_str):
    """Return number of days in 'YYYY-MM'. Fallback: 30."""
    try:
        y, m = map(int, month_str.split('-'))
        return calendar.monthrange(y, m)[1]
    except Exception:
        return 30


def _active_sites_count():
    """Number of active sites — used to split global overhead."""
    try:
        return max(1, Site.query.filter_by(active=True).count() or 1)
    except Exception:
        return 1


def _normalize_frequency(freq):
    """Force a valid frequency string, or return None."""
    if not freq:
        return None
    f = str(freq).lower().strip()
    if f in ('daily', 'weekly', 'monthly', 'quarterly', 'yearly'):
        return f
    return None


def _row_frequency(row):
    """
    Resolve the effective frequency for an overhead row.

    Priority:
      1. row.frequency (if set and valid)
      2. row.category.default_frequency (via relationship)
      3. row.category_id → OverheadCategory.default_frequency (FK lookup)
      4. row.category_name → OverheadCategory.name → default_frequency
      5. 'monthly' (safe default)
    """
    # 1. Direct
    f = _normalize_frequency(getattr(row, 'frequency', None))
    if f:
        return f

    # 2. Via relationship
    try:
        cat = getattr(row, 'category', None)
        if cat is not None:
            f = _normalize_frequency(getattr(cat, 'default_frequency', None))
            if f:
                return f
    except Exception:
        pass

    # 3. Via FK
    cat_id = getattr(row, 'category_id', None)
    if cat_id:
        try:
            from models import OverheadCategory
            c = OverheadCategory.query.get(cat_id)
            if c:
                f = _normalize_frequency(getattr(c, 'default_frequency', None))
                if f:
                    return f
        except Exception:
            pass

    # 4. Via name
    cat_name = getattr(row, 'category_name', None)
    if cat_name:
        try:
            from models import OverheadCategory
            c = OverheadCategory.query.filter_by(name=cat_name).first()
            if c:
                f = _normalize_frequency(getattr(c, 'default_frequency', None))
                if f:
                    return f
        except Exception:
            pass

    # 5. Default
    return 'monthly'


def _row_working_days(row, fallback):
    """Working days for this row — prefer the row's own value, else fallback."""
    try:
        wd = int(getattr(row, 'working_days', None) or 0)
        if wd > 0:
            return wd
    except Exception:
        pass
    return max(1, int(fallback or 26))


def _monthly_total_for_row(row):
    """
    Monthly total for a single overhead row, respecting its frequency.

      daily     → amount × working_days     (e.g. 5 × 26 = 130)
      weekly    → amount × ceil(wd / 7)
      quarterly → amount / 3
      yearly    → amount / 12
      monthly   → amount (default)
    """
    amt = max(0.0, float(getattr(row, 'amount', 0) or 0))
    if amt == 0:
        return 0.0

    wd = _row_working_days(row, 26)
    freq = _row_frequency(row)

    if freq == 'daily':
        return amt * wd
    if freq == 'weekly':
        return amt * max(1, math.ceil(wd / 7))
    if freq == 'quarterly':
        return amt / 3.0
    if freq == 'yearly':
        return amt / 12.0
    return amt


def _daily_for_row(row, wd_fallback=None):
    """
    Daily cost for a single row = monthly_total ÷ its working_days.

    For a 'daily' row this returns the amount unchanged (e.g. 5.000).
    For 'monthly' it returns amount / wd.
    """
    amt = max(0.0, float(getattr(row, 'amount', 0) or 0))
    if amt == 0:
        return 0.0

    # ⭐ Always use the row's own working_days if set, else fallback
    wd = _row_working_days(row, wd_fallback or 26)
    monthly = _monthly_total_for_row(row)
    return monthly / wd


def _sum_daily(rows, wd_fallback=None):
    """Sum the frequency-aware daily cost across a list of rows."""
    return sum(_daily_for_row(r, wd_fallback) for r in rows)


def calculate_daily_overhead(month, site_id=None, site_ids_for_month=None):
    """
    Daily overhead (BD) for a given site in a given month.

    Frequencies handled:
      daily     → amount (as-is per day)
      weekly    → amount × ceil(working_days / 7) / working_days
      quarterly → (amount / 3) / working_days
      yearly    → (amount / 12) / working_days
      monthly   → amount / working_days (default)
    """
    try:
        days_in_month = _days_in_month(month)

        # ── Determine how many sites to split global overhead across ──
        if site_ids_for_month:
            sites_count = max(1, len(set(site_ids_for_month)))
        else:
            sites_count = _active_sites_count()

        # ─────────────────────────────────────────────
        # 1. SITE-SPECIFIC rows
        # ─────────────────────────────────────────────
        if site_id:
            site_rows = MonthlyOverhead.query.filter_by(
                month=month, site_id=site_id
            ).all()

            if site_rows:
                # A site-specific row is already scoped to this site, so we
                # do NOT divide by sites_count again.
                return _sum_daily(site_rows, wd_fallback=days_in_month)

        # ─────────────────────────────────────────────
        # 2. GLOBAL rows (site_id IS NULL)
        # ─────────────────────────────────────────────
        global_rows = MonthlyOverhead.query.filter_by(
            month=month, site_id=None
        ).all()

        if global_rows:
            total_daily = _sum_daily(global_rows, wd_fallback=days_in_month)
            return total_daily / sites_count

        # ─────────────────────────────────────────────
        # 3. Fallback: any row for the month
        # ─────────────────────────────────────────────
        all_rows = MonthlyOverhead.query.filter_by(month=month).all()
        if all_rows:
            total_daily = _sum_daily(all_rows, wd_fallback=days_in_month)
            return total_daily / sites_count

        # ─────────────────────────────────────────────
        # 4. Setting-based fallback
        # ─────────────────────────────────────────────
        monthly_overhead = 0.0
        try:
            setting = Setting.query.filter_by(key='monthly_overhead').first()
            if setting and setting.value not in (None, ''):
                monthly_overhead = float(setting.value)
        except Exception as inner:
            print(f"[helpers] Setting lookup failed: {inner}")

        if monthly_overhead > 0:
            return (monthly_overhead / days_in_month) / sites_count

        return 0.0

    except Exception as e:
        print(f"[helpers] calculate_daily_overhead failed: {e}")
        import traceback
        traceback.print_exc()
        return 0.0