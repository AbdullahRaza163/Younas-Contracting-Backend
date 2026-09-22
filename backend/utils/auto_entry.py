# utils/auto_entry.py
"""
Auto-entry computation.

Aggregates per (date, site):
  * labour      ← attendance records, SPLIT BY SHIFT for multi-site days
  * one_time    ← non-recurring expenses
  * material    ← expenses categorized as material
  * equipment   ← expenses categorized as equipment
  * transport   ← expenses categorized as transport
  * other       ← any other non-recurring expense
  * overhead    ← daily share of monthly overhead (frequency-aware)
  * kamai       ← invoices issued on that date

RULE: Only return a row for a site if there is at least one piece of real
activity that day (attendance, invoice, or expense). This prevents negative
phantom entries on days with no work.
"""
import calendar
import math
import time
from datetime import datetime, date as date_cls, timezone

from models import db, Attendance, Worker, Site, Expense, Invoice, MonthlyOverhead
from models.attendance_settings import AttendanceSettings


# ============================================
# ⭐ MODULE-LEVEL CACHES (TTL-based)
# ============================================
_SETTINGS_CACHE = {'ts': 0, 'val': None}
_SETTINGS_TTL = 5  # ⭐ was 30 — now 5s

_SITES_CACHE = {'ts': 0, 'val': None}
_SITES_TTL = 5  # ⭐ was 60 — now 5s

# Overhead cache: key = (month_key, site_id or '_GLOBAL_', active_sites_count)
_OH_CACHE = {}
_OH_TTL = 5  # ⭐ was 60 — now 5s


def _cache_get(cache, key, ttl):
    entry = cache.get(key)
    if not entry:
        return None
    ts, val = entry
    if time.time() - ts > ttl:
        cache.pop(key, None)
        return None
    return val


def _cache_set(cache, key, val):
    cache[key] = (time.time(), val)


def clear_auto_entry_caches():
    """Call this after attendance/invoice/expense/overhead changes to force fresh compute."""
    _OH_CACHE.clear()
    _SITES_CACHE['ts'] = 0
    _SETTINGS_CACHE['ts'] = 0


# ============================================
# SETTINGS CACHE
# ============================================
def _load_settings():
    """Load attendance settings once per TTL window — safe defaults."""
    cached = _cache_get(_SETTINGS_CACHE, 'val', _SETTINGS_TTL)
    if cached is not None:
        return cached

    defaults = {
        'shift_hours': 8.0,
        'break_enabled': True,
        'break_hours': 1.0,
        'overtime_enabled': True,
        'overtime_rate': 1.0,
    }
    try:
        s = AttendanceSettings.get_settings()
        if not s:
            result = defaults
        else:
            result = {
                'shift_hours': float(getattr(s, 'shift_hours', None) or defaults['shift_hours']),
                'break_enabled': bool(getattr(s, 'break_enabled', defaults['break_enabled'])),
                'break_hours': float(getattr(s, 'break_hours', None) or 0),
                'overtime_enabled': bool(getattr(s, 'overtime_enabled', defaults['overtime_enabled'])),
                'overtime_rate': float(getattr(s, 'overtime_rate', None) or defaults['overtime_rate']),
            }
    except Exception as e:
        print(f"[auto_entry] _load_settings failed: {e}")
        result = defaults

    _cache_set(_SETTINGS_CACHE, 'val', result)
    return result


# ============================================
# SITES CACHE
# ============================================
def _get_active_sites_cached():
    """Cache active sites for 5s to avoid repeated queries."""
    cached = _cache_get(_SITES_CACHE, 'val', _SITES_TTL)
    if cached is not None:
        return cached
    val = Site.query.filter_by(active=True).all()
    _cache_set(_SITES_CACHE, 'val', val)
    return val


def _get_sites_for_call(site_id):
    """Return the sites list for this compute call."""
    if site_id:
        cached = _cache_get(_SITES_CACHE, 'val', _SITES_TTL)
        if cached is not None:
            found = [s for s in cached if s.id == site_id]
            if found:
                return found
        return Site.query.filter_by(id=site_id).all()
    return _get_active_sites_cached()


# ============================================
# SHIFT-LEVEL HOURS + WAGE
# ============================================
def _naive_utc(dt):
    """Normalize any datetime to naive UTC."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _shift_hours(shift, settings):
    """
    Compute paid hours for ONE shift, honoring per-shift break/OT toggles.
    `shift` may be an AttendanceShift object OR a legacy Attendance record.
    """
    if not shift:
        return 0.0

    ci = _naive_utc(getattr(shift, 'checked_in', None))
    co = _naive_utc(getattr(shift, 'checked_out', None))
    if not ci or not co:
        return 0.0

    seconds = (co - ci).total_seconds()
    if seconds <= 0:
        return 0.0

    break_enabled = getattr(shift, 'break_enabled', None)
    if break_enabled is None:
        break_enabled = settings.get('break_enabled', True)

    if break_enabled:
        bs = _naive_utc(getattr(shift, 'break_start', None))
        be = _naive_utc(getattr(shift, 'break_end', None))
        if bs and be:
            bsec = (be - bs).total_seconds()
            if bsec > 0:
                seconds -= bsec

    return max(0.0, seconds / 3600.0)


def _hourly_rate_for(worker, settings):
    """Resolve hourly rate: prefer worker.hourly_rate, else daily_rate / shift_hours."""
    if not worker:
        return 0.0
    hourly = float(getattr(worker, 'hourly_rate', 0) or 0)
    if hourly > 0:
        return hourly
    daily = float(getattr(worker, 'daily_rate', 0) or 0)
    if daily > 0:
        shift_hours = float(settings.get('shift_hours', 8.0)) or 8.0
        return daily / shift_hours
    return 0.0


def _wage_for_hours(hours, hourly, settings, ot_enabled=True):
    """Compute wage for a given number of hours, respecting the OT split."""
    if hours <= 0 or hourly <= 0:
        return 0.0

    shift_hours = float(settings.get('shift_hours', 8.0)) or 8.0
    ot_rate = float(settings.get('overtime_rate', 1.0)) or 1.0

    if ot_enabled and hours > shift_hours:
        normal = shift_hours
        ot = hours - shift_hours
        return normal * hourly + ot * hourly * ot_rate
    return hours * hourly


# ============================================
# OVERHEAD HELPERS — FREQUENCY-AWARE
# ============================================
def _days_in_month(entry_date):
    try:
        return calendar.monthrange(entry_date.year, entry_date.month)[1]
    except Exception:
        return 30


def _compute_monthly_total(amount, frequency, working_days):
    """Return the MONTHLY total for one overhead row, respecting its frequency."""
    amt = max(0.0, float(amount or 0))
    wd = max(1, int(working_days or 26))
    f = str(frequency or 'monthly').lower().strip()

    if f == 'daily':
        return amt * wd
    if f == 'weekly':
        return amt * max(1, math.ceil(wd / 7))
    if f == 'quarterly':
        return amt / 3.0
    if f == 'yearly':
        return amt / 12.0
    return amt


def _daily_for_row(row):
    """Return the per-day cost for a single overhead row."""
    amt = max(0.0, float(getattr(row, 'amount', 0) or 0))
    wd = max(1, int(getattr(row, 'working_days', 26) or 26))
    freq = getattr(row, 'frequency', None) or 'monthly'
    monthly = _compute_monthly_total(amt, freq, wd)
    return monthly / wd


def _resolve_overhead_rows(month_key, site_id):
    """
    Return the list of MonthlyOverhead rows that apply to (month, site).
    Also returns whether the total should be split across active sites.
    """
    def _query(filters):
        return MonthlyOverhead.query.filter(*filters).all()

    try:
        if site_id:
            site_rows = _query([
                MonthlyOverhead.month == month_key,
                MonthlyOverhead.site_id == site_id,
            ])
            if site_rows:
                return site_rows, False

        global_rows = _query([
            MonthlyOverhead.month == month_key,
            MonthlyOverhead.site_id.is_(None),
        ])
        if global_rows:
            return global_rows, bool(site_id)

        any_rows = _query([MonthlyOverhead.month == month_key])
        if any_rows:
            return any_rows, bool(site_id)
    except Exception as e:
        print(f"[auto_entry] _resolve_overhead_rows failed: {e}")

    return [], False


def _resolve_overhead_for_site(entry_date, site_id, active_sites_count_today):
    """
    Return daily overhead (BD) for the given site/date, frequency-aware.
    ⭐ Memoized per (month, site, sites_count) for 5s.
    """
    month_key = entry_date.strftime('%Y-%m')
    cache_key = (month_key, site_id or '_GLOBAL_', int(active_sites_count_today or 1))

    cached = _cache_get(_OH_CACHE, cache_key, _OH_TTL)
    if cached is not None:
        return cached

    rows, needs_split = _resolve_overhead_rows(month_key, site_id)

    if not rows:
        _cache_set(_OH_CACHE, cache_key, 0.0)
        return 0.0

    total_daily = sum(_daily_for_row(r) for r in rows)

    if needs_split:
        n = max(1, int(active_sites_count_today or 1))
        result = total_daily / n
    else:
        result = total_daily

    _cache_set(_OH_CACHE, cache_key, result)
    return result


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

    settings = _load_settings()

    # -------- Which sites to consider --------
    sites = _get_sites_for_call(site_id)
    if not sites:
        return []

    site_ids = [s.id for s in sites]

    # -------- 1. LABOUR — from attendance (MULTI-SHIFT AWARE) --------
    attendance_rows = Attendance.query.filter(
        Attendance.date == entry_date,
    ).all()

    worker_ids = list({a.worker_id for a in attendance_rows if a.worker_id})
    workers_by_id = {}
    if worker_ids:
        workers_batch = Worker.query.filter(Worker.id.in_(worker_ids)).all()
        workers_by_id = {w.id: w for w in workers_batch}

    shifts_by_att = {}
    try:
        from models.attendance_shift import AttendanceShift
        att_ids = [a.id for a in attendance_rows]
        if att_ids:
            all_shifts = AttendanceShift.query.filter(
                AttendanceShift.attendance_id.in_(att_ids)
            ).order_by(AttendanceShift.order_index).all()
            for sh in all_shifts:
                shifts_by_att.setdefault(sh.attendance_id, []).append(sh)
    except Exception as e:
        print(f"[auto_entry] shift preload failed: {e}")
        shifts_by_att = {}

    labour_by_site = {sid: 0.0 for sid in site_ids}
    has_activity_by_site = {sid: False for sid in site_ids}

    for a in attendance_rows:
        worker = workers_by_id.get(a.worker_id)
        hourly = _hourly_rate_for(worker, settings)

        shifts = shifts_by_att.get(a.id, [])
        if len(shifts) > 0:
            for sh in shifts:
                sid = getattr(sh, 'site_id', None) or a.site_id
                if sid not in labour_by_site:
                    continue

                hours = _shift_hours(sh, settings)
                if hours <= 0:
                    continue

                ot_enabled = getattr(sh, 'overtime_enabled', None)
                if ot_enabled is None:
                    ot_enabled = settings.get('overtime_enabled', True)

                wage = _wage_for_hours(hours, hourly, settings, ot_enabled)
                labour_by_site[sid] += wage
                has_activity_by_site[sid] = True
            continue

        sid = a.site_id
        if sid not in labour_by_site:
            continue

        wage = float(a.wage_earned or 0)
        if wage <= 0:
            hours = _shift_hours(a, settings)
            wage = _wage_for_hours(hours, hourly, settings, settings.get('overtime_enabled', True))

        labour_by_site[sid] += wage
        has_activity_by_site[sid] = True

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

    # -------- 4. OVERHEAD — FREQUENCY-AWARE (CACHED) --------
    active_sites_today = [sid for sid, has in has_activity_by_site.items() if has]
    active_sites_count_today = max(1, len(active_sites_today))

    overhead_by_site = {sid: 0.0 for sid in site_ids}
    for sid in active_sites_today:
        oh = _resolve_overhead_for_site(entry_date, sid, active_sites_count_today)
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