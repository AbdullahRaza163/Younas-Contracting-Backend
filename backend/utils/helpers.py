# utils/helpers.py
import random
import string
import calendar
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
# DAILY OVERHEAD CALCULATION
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


def calculate_daily_overhead(month, site_id=None, site_ids_for_month=None):
    """
    Daily overhead (BD) for a given site in a given month.

    Priority:
      1. Site-specific row in monthly_overhead for that (month, site_id).
      2. Global row (site_id IS NULL) for that month.
      3. Sum of all rows for that month → divided by active-sites count.
      4. Setting row 'monthly_overhead' → divided by active-sites count.
      5. Return 0 (no phantom fallback).

    `site_ids_for_month` — optional list of site IDs that had activity this
    month. When provided, global overhead is split across only those sites
    instead of all active sites.
    """
    try:
        days_in_month = _days_in_month(month)

        # ── Determine how many sites to split global overhead across ──
        if site_ids_for_month:
            sites_count = max(1, len(set(site_ids_for_month)))
        else:
            sites_count = _active_sites_count()

        # ─────────────────────────────────────────────
        # 1. SITE-SPECIFIC row
        # ─────────────────────────────────────────────
        if site_id:
            site_rows = MonthlyOverhead.query.filter_by(
                month=month, site_id=site_id
            ).all()

            if site_rows:
                total = sum(float(r.amount or 0) for r in site_rows)
                # If the site row already carries working_days + sites_count, use them
                first = site_rows[0]
                wd = float(first.working_days or days_in_month) or days_in_month
                sc = float(first.sites_count or 1) or 1
                # A site-specific row is already scoped to this site,
                # so we do NOT divide by sites_count again.
                return total / wd

        # ─────────────────────────────────────────────
        # 2. GLOBAL row (site_id IS NULL)
        # ─────────────────────────────────────────────
        global_rows = MonthlyOverhead.query.filter_by(
            month=month, site_id=None
        ).all()

        if global_rows:
            total = sum(float(r.amount or 0) for r in global_rows)
            first = global_rows[0]
            wd = float(first.working_days or days_in_month) or days_in_month
            return (total / wd) / sites_count

        # ─────────────────────────────────────────────
        # 3. Fallback: sum ALL rows for the month, split across sites
        # ─────────────────────────────────────────────
        all_rows = MonthlyOverhead.query.filter_by(month=month).all()
        if all_rows:
            total = sum(float(r.amount or 0) for r in all_rows)
            wd = float(all_rows[0].working_days or days_in_month) or days_in_month
            return (total / wd) / sites_count

        # ─────────────────────────────────────────────
        # 4. Setting-based fallback (never phantom 194)
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

        # ─────────────────────────────────────────────
        # 5. No data → 0
        # ─────────────────────────────────────────────
        return 0.0

    except Exception as e:
        print(f"[helpers] calculate_daily_overhead failed: {e}")
        return 0.0