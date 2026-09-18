# utils/auto_entry.py
"""
Auto-entry computation.

Aggregates per (date, site):
  * labour      ← attendance records (wageEarned, or hours × hourly_rate)
  * one_time    ← non-recurring expenses
  * material    ← expenses categorized as material
  * equipment   ← expenses categorized as equipment
  * transport   ← expenses categorized as transport
  * other       ← any other non-recurring expense
  * overhead    ← daily share of monthly overhead
  * kamai       ← invoices issued on that date

RULE: Only return a row for a site if there is at least one piece of real
activity that day (attendance, invoice, or expense). This prevents negative
phantom entries on days with no work.
"""
import calendar
from datetime import datetime, date as date_cls

from models import db, Attendance, Worker, Site, Expense, Invoice, MonthlyOverhead


# ============================================
# OVERHEAD HELPERS
# ============================================
def _days_in_month(entry_date):
    try:
        return calendar.monthrange(entry_date.year, entry_date.month)[1]
    except Exception:
        return 30


def _resolve_overhead_for_site(entry_date, site_id, sites_count):
    """
    Return daily overhead (BD) for the given site/date.

    Uses `calculate_daily_overhead` from utils.helpers, which now:
      1. Prefers site-specific rows for that month
      2. Falls back to global (site_id IS NULL) rows
      3. Falls back to any row for the month (split across sites)
      4. Falls back to Setting.monthly_overhead
      5. Returns 0 (no phantom)
    """
    try:
        from utils.helpers import calculate_daily_overhead
        month_key = entry_date.strftime('%Y-%m')
        return float(calculate_daily_overhead(month_key, site_id=site_id) or 0)
    except Exception as e:
        print(f"[auto_entry] overhead failed for {site_id} on {entry_date}: {e}")
        return 0.0


def _resolve_global_daily_overhead(entry_date, active_sites_today):
    """
    When no site-specific row exists, we pull the global monthly overhead
    once and split it across the sites that had activity today.
    """
    try:
        from utils.helpers import calculate_daily_overhead
        month_key = entry_date.strftime('%Y-%m')
        n = max(1, len(active_sites_today))
        # Passing site_id=None → global row path.
        # Then divide the returned global daily total across today's active sites.
        total_daily_global = float(
            calculate_daily_overhead(month_key, site_id=None) or 0
        )
        # calculate_daily_overhead already divides by active_sites_count,
        # so we scale it back up to the global total, then split by today's sites.
        try:
            active_total = max(1, Site.query.filter_by(active=True).count() or 1)
        except Exception:
            active_total = 1
        global_daily_total = total_daily_global * active_total
        return global_daily_total / n
    except Exception as e:
        print(f"[auto_entry] global overhead failed: {e}")
        return 0.0


# ============================================
# MAIN
# ============================================
def compute_auto_entries(entry_date, site_id=None):
    """
    Compute auto-entry values for a given date.
    Only returns rows for sites with activity that day.
    """
    if isinstance(entry_date, str):
        entry_date = datetime.strptime(entry_date, '%Y-%m-%d').date()

    # -------- Which sites to consider --------
    if site_id:
        sites = Site.query.filter_by(id=site_id).all()
    else:
        sites = Site.query.filter_by(active=True).all()

    if not sites:
        return []

    site_ids = [s.id for s in sites]

    # -------- 1. LABOUR — from attendance --------
    attendance_rows = Attendance.query.filter(
        Attendance.date == entry_date,
        Attendance.site_id.in_(site_ids),
    ).all()

    labour_by_site = {sid: 0.0 for sid in site_ids}
    has_activity_by_site = {sid: False for sid in site_ids}

    for a in attendance_rows:
        wage = float(a.wage_earned or 0)
        if wage == 0 and a.checked_in and a.checked_out:
            worker = Worker.query.get(a.worker_id)
            if worker:
                hours = (a.checked_out - a.checked_in).total_seconds() / 3600
                # Respect break_enabled on the record
                break_enabled = getattr(a, 'break_enabled', None)
                if break_enabled is None:
                    break_enabled = True  # default
                if break_enabled and a.break_start and a.break_end:
                    hours -= (a.break_end - a.break_start).total_seconds() / 3600
                hours = max(hours, 0)
                wage = hours * float(worker.hourly_rate or 0)
        labour_by_site[a.site_id] = labour_by_site.get(a.site_id, 0) + wage
        has_activity_by_site[a.site_id] = True

    # -------- 2. EXPENSES --------
    expense_rows = Expense.query.filter(
        Expense.date == entry_date,
        Expense.site_id.in_(site_ids),
    ).all()

    one_time_by_site  = {sid: 0.0 for sid in site_ids}
    material_by_site  = {sid: 0.0 for sid in site_ids}
    equipment_by_site = {sid: 0.0 for sid in site_ids}
    transport_by_site = {sid: 0.0 for sid in site_ids}
    other_by_site     = {sid: 0.0 for sid in site_ids}

    for e in expense_rows:
        sid = e.site_id
        if sid not in one_time_by_site:
            continue
        amount = float(e.amount or 0)
        cat = (e.category or '').lower()
        if cat in ('material', 'materials'):
            material_by_site[sid] += amount
        elif cat in ('equipment', 'machinery'):
            equipment_by_site[sid] += amount
        elif cat in ('transport', 'fuel', 'vehicle'):
            transport_by_site[sid] += amount
        elif e.is_recurring:
            # Recurring expense — treated as part of overhead, skip
            pass
        else:
            one_time_by_site[sid] += amount
        has_activity_by_site[sid] = True

    # -------- 3. KAMAI — from invoices --------
    try:
        invoice_rows = Invoice.query.filter(
            Invoice.invoice_date == entry_date,
            Invoice.site_id.in_(site_ids),
        ).all()
    except Exception as e:
        print(f"[auto_entry] INVOICE QUERY FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise

    kamai_by_site = {sid: 0.0 for sid in site_ids}
    for inv in invoice_rows:
        sid = getattr(inv, 'site_id', None)
        if sid in kamai_by_site:
            amount = float(
                getattr(inv, 'total_amount', None)
                or getattr(inv, 'amount', None)
                or 0
            )
            kamai_by_site[sid] += amount
            has_activity_by_site[sid] = True

    # -------- 4. OVERHEAD --------
    # Determine which sites had activity today (these share the overhead)
    active_sites_today = [sid for sid, has in has_activity_by_site.items() if has]
    active_sites_count_today = max(1, len(active_sites_today))

    overhead_by_site = {sid: 0.0 for sid in site_ids}

    for sid in active_sites_today:
        # First try a site-specific row for this month
        oh = _resolve_overhead_for_site(entry_date, sid, active_sites_count_today)

        # If the site row wasn't present, this returns the global total
        # split by active sites. Either way, `oh` is the per-site amount now.
        overhead_by_site[sid] = float(oh or 0)

    # -------- 5. Assemble — SKIP sites with no activity --------
    result = []
    for s in sites:
        sid = s.id
        if not has_activity_by_site.get(sid):
            continue

        kamai     = round(kamai_by_site.get(sid, 0), 3)
        labour    = round(labour_by_site.get(sid, 0), 3)
        one_time  = round(one_time_by_site.get(sid, 0), 3)
        material  = round(material_by_site.get(sid, 0), 3)
        equipment = round(equipment_by_site.get(sid, 0), 3)
        transport = round(transport_by_site.get(sid, 0), 3)
        other     = round(other_by_site.get(sid, 0), 3)
        overhead  = round(overhead_by_site.get(sid, 0), 3)

        profit = (
            kamai - labour - overhead - one_time
            - material - equipment - transport - other
        )

        result.append({
            'date':          entry_date.isoformat(),
            'siteId':        sid,
            'siteName':      s.name,
            'kamai':         kamai,
            'labour':        labour,
            'overhead':      overhead,
            'oneTime':       one_time,
            'materialCost':  material,
            'equipmentCost': equipment,
            'transportCost': transport,
            'otherExpense':  other,
            'profit':        round(profit, 3),
            'source':        'auto',
            'note':          'Auto-computed from attendance, expenses & invoices',
        })

    return result