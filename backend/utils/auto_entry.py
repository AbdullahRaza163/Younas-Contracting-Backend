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
from datetime import datetime, date as date_cls
from models import db, Attendance, Worker, Site, Expense, Invoice


def _daily_overhead_for_site(entry_date, site_id, sites_count):
    """Daily overhead share for one site."""
    try:
        from utils.helpers import calculate_daily_overhead
        month_key = entry_date.strftime('%Y-%m')
        return float(calculate_daily_overhead(month_key, site_id) or 0)
    except Exception:
        from models import Setting
        row = Setting.query.filter_by(key='monthly_overhead').first()
        monthly = float(row.value) if row and row.value else 0.0
        days_in_month = 30
        try:
            import calendar
            days_in_month = calendar.monthrange(entry_date.year, entry_date.month)[1]
        except Exception:
            pass
        if sites_count <= 0 or days_in_month <= 0:
            return 0.0
        return monthly / sites_count / days_in_month


def compute_auto_entries(entry_date, site_id=None):
    """
    Compute auto-entry values for a given date.
    Only returns rows for sites with activity that day.
    """
    if isinstance(entry_date, str):
        entry_date = datetime.strptime(entry_date, '%Y-%m-%d').date()

    # Which sites to consider
    if site_id:
        sites = Site.query.filter_by(id=site_id).all()
    else:
        sites = Site.query.filter_by(active=True).all()

    if not sites:
        return []

    sites_count = len(sites)
    site_ids = [s.id for s in sites]

    # ------------------------------------------------------------------
    # 1. LABOUR — from attendance
    # ------------------------------------------------------------------
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
                if a.break_start and a.break_end:
                    hours -= (a.break_end - a.break_start).total_seconds() / 3600
                hours = max(hours, 0)
                wage = hours * float(worker.hourly_rate or 0)
        labour_by_site[a.site_id] = labour_by_site.get(a.site_id, 0) + wage
        has_activity_by_site[a.site_id] = True

    # ------------------------------------------------------------------
    # 2. ONE-TIME / MATERIAL / EQUIPMENT / TRANSPORT / OTHER — from expenses
    # ------------------------------------------------------------------
    expense_rows = Expense.query.filter(Expense.date == entry_date).all()

    one_time_by_site = {sid: 0.0 for sid in site_ids}
    material_by_site = {sid: 0.0 for sid in site_ids}
    equipment_by_site = {sid: 0.0 for sid in site_ids}
    transport_by_site = {sid: 0.0 for sid in site_ids}
    other_by_site = {sid: 0.0 for sid in site_ids}

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

    # ------------------------------------------------------------------
    # 3. KAMAI — from invoices
    # ------------------------------------------------------------------
    try:
        invoice_rows = Invoice.query.filter(Invoice.invoice_date == entry_date).all()
    except Exception:
        invoice_rows = []

    kamai_by_site = {sid: 0.0 for sid in site_ids}
    for inv in invoice_rows:
        sid = getattr(inv, 'site_id', None)
        if sid in kamai_by_site:
            kamai_by_site[sid] += float(inv.total_amount or 0)
            has_activity_by_site[sid] = True

    # ------------------------------------------------------------------
    # 4. OVERHEAD — daily share per site (only applied when site had activity)
    # ------------------------------------------------------------------
    overhead_per_site = _daily_overhead_for_site(entry_date, None, sites_count)

    # ------------------------------------------------------------------
    # 5. Assemble — SKIP sites with no activity
    # ------------------------------------------------------------------
    result = []
    for s in sites:
        sid = s.id

        # ⬇️ KEY CHANGE: skip sites with no activity
        if not has_activity_by_site.get(sid):
            continue

        kamai = round(kamai_by_site.get(sid, 0), 3)
        labour = round(labour_by_site.get(sid, 0), 3)
        one_time = round(one_time_by_site.get(sid, 0), 3)
        material = round(material_by_site.get(sid, 0), 3)
        equipment = round(equipment_by_site.get(sid, 0), 3)
        transport = round(transport_by_site.get(sid, 0), 3)
        other = round(other_by_site.get(sid, 0), 3)
        overhead = round(overhead_per_site, 3)

        profit = (
            kamai - labour - overhead - one_time
            - material - equipment - transport - other
        )

        result.append({
            'date': entry_date.isoformat(),
            'siteId': sid,
            'siteName': s.name,
            'kamai': kamai,
            'labour': labour,
            'overhead': overhead,
            'oneTime': one_time,
            'materialCost': material,
            'equipmentCost': equipment,
            'transportCost': transport,
            'otherExpense': other,
            'profit': round(profit, 3),
            'source': 'auto',
            'note': 'Auto-computed from attendance, expenses & invoices',
        })

    return result