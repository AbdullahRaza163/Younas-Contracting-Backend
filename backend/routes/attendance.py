# routes/attendance.py
from flask import request, jsonify
from datetime import datetime, timedelta, timezone
from calendar import monthrange
from models import db, Attendance, Worker, WorkerTeam, TeamMember, Site
from models.attendance_shift import AttendanceShift   # ⭐ NEW
from utils.helpers import generate_id
from routes import attendance_bp
from sqlalchemy import func, and_

from models.attendance_settings import AttendanceSettings


# ============================================
# TIME HELPERS — single source of truth
# ============================================
def utc_now():
    """Return a NAIVE UTC datetime — consistent with what the model stores."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_iso_utc(value):
    """Parse any ISO datetime string → NAIVE UTC datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = value
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _month_bounds(month_str):
    """Return (start_date, end_date) for 'YYYY-MM'."""
    y, m = map(int, month_str.split('-'))
    first = datetime(y, m, 1).date()
    last = datetime(y, m, monthrange(y, m)[1]).date()
    return first, last


# ────────────────────────────────────────────
# ⭐ Settings-aware recalculation
# ────────────────────────────────────────────
def _get_settings_dict():
    """Load attendance settings as a plain dict — safe defaults if missing."""
    defaults = {
        'shift_hours': 8.0,
        'break_enabled': True,
        'break_hours': 1.0,
        'overtime_enabled': True,
        'overtime_rate': 1.5,
    }
    try:
        s = AttendanceSettings.get_settings()
        if not s:
            return defaults
        return {
            'shift_hours': float(getattr(s, 'shift_hours', defaults['shift_hours']) or defaults['shift_hours']),
            'break_enabled': bool(getattr(s, 'break_enabled', defaults['break_enabled'])),
            'break_hours': float(getattr(s, 'break_hours', defaults['break_hours']) or 0),
            'overtime_enabled': bool(getattr(s, 'overtime_enabled', defaults['overtime_enabled'])),
            'overtime_rate': float(getattr(s, 'overtime_rate', defaults['overtime_rate']) or defaults['overtime_rate']),
        }
    except Exception as e:
        print(f"[_get_settings_dict] falling back to defaults: {e}")
        return defaults


def _resolve_break_enabled(record, settings):
    """Per-record override → global setting."""
    v = getattr(record, 'break_enabled', None)
    if v is not None:
        return bool(v)
    return bool(settings.get('break_enabled', True))


def _resolve_overtime_enabled(record, settings):
    """Per-record override → global setting."""
    v = getattr(record, 'overtime_enabled', None)
    if v is not None:
        return bool(v)
    return bool(settings.get('overtime_enabled', True))


def _recalc_record(record, worker=None, settings=None):
    """
    Recompute hours + wage for a single attendance record.

    ⭐ If the record has `shifts`, we aggregate them (multi-site day).
    Otherwise, we fall back to the legacy single-session calculation.
    """
    if settings is None:
        settings = _get_settings_dict()

    # ⭐ Multi-site path
    has_shifts = AttendanceShift.query.filter_by(attendance_id=record.id).count() > 0
    if has_shifts:
        record.recalc_from_shifts(settings)
        return

    # ── Legacy single-session path ──
    if not (record.checked_in and record.checked_out):
        record.total_hours = 0.0
        record.normal_hours = 0.0
        record.overtime_hours = 0.0
        record.wage_earned = 0.0
        return

    ci = record.checked_in
    co = record.checked_out
    if ci.tzinfo is not None:
        ci = ci.astimezone(timezone.utc).replace(tzinfo=None)
    if co.tzinfo is not None:
        co = co.astimezone(timezone.utc).replace(tzinfo=None)

    total_seconds = (co - ci).total_seconds()
    if total_seconds < 0:
        total_seconds = 0

    break_enabled = _resolve_break_enabled(record, settings)
    if break_enabled and record.break_start and record.break_end:
        bs = record.break_start
        be = record.break_end
        if bs.tzinfo is not None:
            bs = bs.astimezone(timezone.utc).replace(tzinfo=None)
        if be.tzinfo is not None:
            be = be.astimezone(timezone.utc).replace(tzinfo=None)
        break_seconds = (be - bs).total_seconds()
        if break_seconds > 0:
            total_seconds -= break_seconds

    total_hours = max(0.0, total_seconds / 3600.0)
    record.total_hours = round(total_hours, 2)

    overtime_enabled = _resolve_overtime_enabled(record, settings)
    shift_hours = float(settings.get('shift_hours', 8.0)) or 8.0

    if overtime_enabled and total_hours > shift_hours:
        record.normal_hours = round(shift_hours, 2)
        record.overtime_hours = round(total_hours - shift_hours, 2)
    else:
        record.normal_hours = round(total_hours, 2)
        record.overtime_hours = 0.0

    if worker is None:
        worker = Worker.query.get(record.worker_id)

    if worker:
        hourly_rate = float(getattr(worker, 'hourly_rate', 0) or 0)
        if not hourly_rate:
            daily_rate = float(getattr(worker, 'daily_rate', 0) or 0)
            if daily_rate and shift_hours:
                hourly_rate = daily_rate / shift_hours

        base_wage = (record.normal_hours or 0) * hourly_rate
        ot_rate = float(settings.get('overtime_rate', 1.5)) or 1.5
        if overtime_enabled:
            ot_wage = (record.overtime_hours or 0) * hourly_rate * ot_rate
        else:
            ot_wage = (record.overtime_hours or 0) * hourly_rate
        record.wage_earned = round(max(0.0, base_wage + ot_wage), 2)
    else:
        record.wage_earned = 0.0


# ============================================
# GET /attendance
# ============================================
@attendance_bp.route('', methods=['GET'])
def get_attendance():
    """Get all attendance records with optional filters."""
    try:
        date       = request.args.get('date')
        worker_id  = request.args.get('workerId')
        team_id    = request.args.get('teamId')
        site_id    = request.args.get('siteId')
        month      = request.args.get('month')
        start_date = request.args.get('startDate')
        end_date   = request.args.get('endDate')

        query = Attendance.query

        if date:
            query = query.filter(Attendance.date == datetime.strptime(date, '%Y-%m-%d').date())
        if worker_id:
            query = query.filter(Attendance.worker_id == worker_id)
        if team_id:
            query = query.filter(Attendance.team_id == team_id)
        # ⭐ Site filter — also matches any shift site on that day
        if site_id:
            shift_attendance_ids = [
                s.attendance_id for s in
                AttendanceShift.query.filter_by(site_id=site_id).all()
            ]
            query = query.filter(
                (Attendance.site_id == site_id) |
                (Attendance.id.in_(shift_attendance_ids))
            )

        if month:
            start, end = _month_bounds(month)
            query = query.filter(Attendance.date >= start, Attendance.date <= end)
        elif start_date or end_date:
            if start_date:
                query = query.filter(Attendance.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
            if end_date:
                query = query.filter(Attendance.date <= datetime.strptime(end_date, '%Y-%m-%d').date())

        records = query.order_by(Attendance.date.desc(), Attendance.created_at.desc()).all()

        site_ids = list({r.site_id for r in records if r.site_id})
        sites_map = {}
        if site_ids:
            sites = Site.query.filter(Site.id.in_(site_ids)).all()
            sites_map = {s.id: s.name for s in sites}

        worker_ids = list({r.worker_id for r in records if r.worker_id})
        workers_map = {}
        if worker_ids:
            workers = Worker.query.filter(Worker.id.in_(worker_ids)).all()
            workers_map = {w.id: w.name for w in workers}

        result = []
        for r in records:
            d = r.to_dict(
                site_name=sites_map.get(r.site_id) if r.site_id else None,
                worker_name=workers_map.get(r.worker_id)
            )
            result.append(d)
        return jsonify(result)
    except Exception as e:
        print(f"Error in get_attendance: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================
# GET /attendance/team/<team_id>
# ============================================
@attendance_bp.route('/team/<team_id>', methods=['GET'])
def get_team_attendance(team_id):
    try:
        date = request.args.get('date')
        if not date:
            return jsonify({'error': 'Date parameter is required'}), 400
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()

        team_members = TeamMember.query.filter_by(team_id=team_id).all()
        worker_ids = [tm.worker_id for tm in team_members]

        if not worker_ids:
            return jsonify({
                'team_id': team_id, 'date': date, 'members': [],
                'stats': {'total_members': 0, 'present': 0, 'absent': 0,
                          'total_hours': 0, 'total_wages': 0, 'attendance_rate': 0}
            })

        attendance_records = Attendance.query.filter(
            Attendance.worker_id.in_(worker_ids),
            Attendance.date == date_obj
        ).all()

        workers = Worker.query.filter(Worker.id.in_(worker_ids)).all()

        site_ids = list({r.site_id for r in attendance_records if r.site_id})
        # Also include shift site ids
        att_ids = [r.id for r in attendance_records]
        shift_site_ids = list({
            s.site_id for s in
            AttendanceShift.query.filter(AttendanceShift.attendance_id.in_(att_ids)).all()
            if s.site_id
        })
        all_site_ids = list(set(site_ids + shift_site_ids))
        sites_map = {}
        if all_site_ids:
            sites = Site.query.filter(Site.id.in_(all_site_ids)).all()
            sites_map = {s.id: s.name for s in sites}

        att_by_worker = {r.worker_id: r for r in attendance_records}

        result = []
        for worker in workers:
            record = att_by_worker.get(worker.id)
            d = record.to_dict(
                site_name=sites_map.get(record.site_id) if record and record.site_id else None,
            ) if record else None

            hours = float(record.total_hours or 0) if record else 0
            if hours < 0:
                hours = 0

            break_enabled = None
            overtime_enabled = None
            if record:
                break_enabled = getattr(record, 'break_enabled', None)
                overtime_enabled = getattr(record, 'overtime_enabled', None)

            result.append({
                'worker': worker.to_dict(),
                'attendance': d,
                'present': bool(record.present) if record else False,
                'checkedIn': record.checked_in.isoformat() if record and record.checked_in else None,
                'checkedOut': record.checked_out.isoformat() if record and record.checked_out else None,
                'breakStart': record.break_start.isoformat() if record and record.break_start else None,
                'breakEnd': record.break_end.isoformat() if record and record.break_end else None,
                'breakEnabled': break_enabled,
                'overtimeEnabled': overtime_enabled,
                'hoursWorked': hours,
                'wageEarned': float(record.wage_earned or 0) if record else 0,
                'overtimeHours': float(record.overtime_hours or 0) if record else 0,
                'normalHours': float(record.normal_hours or 0) if record else 0,
                'siteId': record.site_id if record else None,
                'siteName': sites_map.get(record.site_id) if record and record.site_id else None,
                # ⭐ Multi-site shifts
                'shifts': (d.get('shifts') if d else []) or [],
                'hasShifts': (d.get('hasShifts') if d else False) or False,
            })

        total_present = sum(1 for r in result if r['present'])
        total_hours = sum(r['hoursWorked'] for r in result)
        total_wages = sum(r['wageEarned'] for r in result)

        return jsonify({
            'team_id': team_id, 'date': date, 'members': result,
            'stats': {
                'total_members': len(result),
                'present': total_present,
                'absent': len(result) - total_present,
                'total_hours': total_hours,
                'total_wages': total_wages,
                'attendance_rate': (total_present / len(result) * 100) if result else 0
            }
        })
    except Exception as e:
        print(f"Error in get_team_attendance: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================
# POST /attendance/team/<team_id>/checkin-all
# ============================================
@attendance_bp.route('/team/<team_id>/checkin-all', methods=['POST'])
def check_in_all_team(team_id):
    try:
        data = request.json or {}
        date_str = data.get('date', utc_now().date().isoformat())
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        site_id = data.get('siteId')
        now = utc_now()

        team_members = TeamMember.query.filter_by(team_id=team_id).all()
        worker_ids = [tm.worker_id for tm in team_members]

        if not worker_ids:
            return jsonify({
                'message': 'No members in this team',
                'checked_in': 0, 'already_checked_in': 0, 'total': 0
            })

        existing = Attendance.query.filter(
            Attendance.worker_id.in_(worker_ids),
            Attendance.date == date_obj
        ).all()
        existing_worker_ids = [r.worker_id for r in existing if r.checked_in is not None]

        created = []
        for worker_id in worker_ids:
            if worker_id not in existing_worker_ids:
                record = Attendance(
                    id=generate_id(),
                    worker_id=worker_id,
                    team_id=team_id,
                    site_id=site_id,
                    date=date_obj,
                    checked_in=now,
                    present=True,
                    notes='Checked in via team bulk action'
                )
                db.session.add(record)
                # ⭐ Also seed the first shift on the given site
                if site_id:
                    db.session.flush()
                    db.session.add(AttendanceShift(
                        id=generate_id(),
                        attendance_id=record.id,
                        site_id=site_id,
                        order_index=0,
                        checked_in=now,
                    ))
                created.append(record)

        db.session.commit()

        return jsonify({
            'message': f'Checked in {len(created)} team members',
            'checked_in': len(created),
            'already_checked_in': len(existing),
            'total': len(worker_ids),
            'siteId': site_id
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error in check_in_all_team: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400


# ============================================
# POST /attendance/team/<team_id>/checkout-all
# ============================================
@attendance_bp.route('/team/<team_id>/checkout-all', methods=['POST'])
def check_out_all_team(team_id):
    try:
        data = request.json or {}
        date_str = data.get('date', utc_now().date().isoformat())
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        team_members = TeamMember.query.filter_by(team_id=team_id).all()
        worker_ids = [tm.worker_id for tm in team_members]

        if not worker_ids:
            return jsonify({
                'message': 'No members in this team',
                'checked_out': 0, 'total_hours': 0, 'total_wages': 0
            })

        records = Attendance.query.filter(
            Attendance.worker_id.in_(worker_ids),
            Attendance.date == date_obj,
            Attendance.checked_in.isnot(None),
            Attendance.checked_out.is_(None)
        ).all()

        workers = Worker.query.filter(Worker.id.in_(worker_ids)).all()
        workers_map = {w.id: w for w in workers}
        settings = _get_settings_dict()

        now = utc_now()
        for record in records:
            if record.checked_in and record.checked_in.tzinfo is not None:
                record.checked_in = record.checked_in.astimezone(timezone.utc).replace(tzinfo=None)

            checkout_time = now
            if record.checked_in and checkout_time < record.checked_in:
                checkout_time = record.checked_in
            record.checked_out = checkout_time

            # ⭐ Close any open shifts too
            open_shifts = AttendanceShift.query.filter(
                AttendanceShift.attendance_id == record.id,
                AttendanceShift.checked_in.isnot(None),
                AttendanceShift.checked_out.is_(None),
            ).all()
            for sh in open_shifts:
                sh.checked_out = checkout_time
            if open_shifts:
                # Multi-site: recalc from shifts
                record.recalc_from_shifts(settings)
            else:
                _recalc_record(record, workers_map.get(record.worker_id), settings)

        db.session.commit()

        total_hours = sum(r.total_hours or 0 for r in records)
        total_wages = sum(r.wage_earned or 0 for r in records)

        return jsonify({
            'message': f'Checked out {len(records)} team members',
            'checked_out': len(records),
            'total_hours': total_hours,
            'total_wages': total_wages
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error in check_out_all_team: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400


# ============================================
# GET /attendance/team-summary/<team_id>
# ============================================
@attendance_bp.route('/team-summary/<team_id>', methods=['GET'])
def get_team_attendance_summary(team_id):
    try:
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        month = request.args.get('month')

        if month:
            start, end = _month_bounds(month)
            start_date, end_date = start.isoformat(), end.isoformat()

        if not start_date or not end_date:
            return jsonify({'error': 'Start date and end date are required'}), 400

        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        team_members = TeamMember.query.filter_by(team_id=team_id).all()
        worker_ids = [tm.worker_id for tm in team_members]

        if not worker_ids:
            return jsonify({
                'team_id': team_id, 'start_date': start_date, 'end_date': end_date,
                'total_days': 0, 'total_workers': 0, 'total_possible_attendance': 0,
                'total_present_days': 0, 'total_hours': 0, 'total_wages': 0,
                'overall_attendance_rate': 0, 'worker_summary': []
            })

        records = Attendance.query.filter(
            Attendance.worker_id.in_(worker_ids),
            Attendance.date >= start,
            Attendance.date <= end
        ).all()

        total_days = (end - start).days + 1
        total_workers = len(worker_ids)
        total_possible = total_days * total_workers

        present_days = sum(1 for r in records if r.present)
        total_hours = sum(max(0, r.total_hours or 0) for r in records)
        total_wages = sum(max(0, r.wage_earned or 0) for r in records)

        by_worker = {}
        for r in records:
            by_worker.setdefault(r.worker_id, []).append(r)

        workers = Worker.query.filter(Worker.id.in_(worker_ids)).all()
        workers_map = {w.id: w for w in workers}

        worker_summary = []
        for worker_id in worker_ids:
            worker_records = by_worker.get(worker_id, [])
            worker = workers_map.get(worker_id)
            if worker:
                present = sum(1 for r in worker_records if r.present)
                worker_summary.append({
                    'worker_id': worker_id,
                    'worker_name': worker.name,
                    'total_present': present,
                    'total_absent': total_days - present,
                    'total_hours': sum(max(0, r.total_hours or 0) for r in worker_records),
                    'total_wages': sum(max(0, r.wage_earned or 0) for r in worker_records),
                    'attendance_rate': (present / total_days * 100) if total_days > 0 else 0
                })

        return jsonify({
            'team_id': team_id, 'start_date': start_date, 'end_date': end_date,
            'total_days': total_days, 'total_workers': total_workers,
            'total_possible_attendance': total_possible,
            'total_present_days': present_days,
            'total_hours': total_hours, 'total_wages': total_wages,
            'overall_attendance_rate': (present_days / total_possible * 100) if total_possible > 0 else 0,
            'worker_summary': worker_summary
        })
    except Exception as e:
        print(f"Error in get_team_attendance_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================
# POST /attendance  — create
# ============================================
@attendance_bp.route('', methods=['POST'])
def create_attendance():
    try:
        data = request.json

        checked_in = parse_iso_utc(data.get('checkedIn'))
        checked_out = parse_iso_utc(data.get('checkedOut'))

        record = Attendance(
            id=generate_id(),
            worker_id=data.get('workerId'),
            team_id=data.get('teamId'),
            site_id=data.get('siteId'),
            date=datetime.strptime(data.get('date'), '%Y-%m-%d').date(),
            checked_in=checked_in,
            checked_out=checked_out,
            present=data.get('present', False),
            notes=data.get('notes', '')
        )

        if 'breakEnabled' in data:
            v = data['breakEnabled']
            record.break_enabled = None if v is None else bool(v)
        if 'overtimeEnabled' in data:
            v = data['overtimeEnabled']
            record.overtime_enabled = None if v is None else bool(v)

        if checked_in and checked_out:
            worker = Worker.query.get(data.get('workerId'))
            _recalc_record(record, worker)

        db.session.add(record)
        db.session.commit()
        return jsonify(record.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_attendance: {str(e)}")
        return jsonify({'error': str(e)}), 400


# ============================================
# GET /attendance/<id>
# ============================================
@attendance_bp.route('/<attendance_id>', methods=['GET'])
def get_attendance_record(attendance_id):
    try:
        record = Attendance.query.get_or_404(attendance_id)
        return jsonify(record.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404


# ============================================
# PUT /attendance/<id>  — general update
# ============================================
@attendance_bp.route('/<attendance_id>', methods=['PUT'])
def update_attendance(attendance_id):
    try:
        record = Attendance.query.get_or_404(attendance_id)
        data = request.json or {}

        if 'checkedIn' in data:
            record.checked_in = parse_iso_utc(data['checkedIn'])
        if 'checkedOut' in data:
            record.checked_out = parse_iso_utc(data['checkedOut'])
        if 'breakStart' in data:
            record.break_start = parse_iso_utc(data['breakStart'])
        if 'breakEnd' in data:
            record.break_end = parse_iso_utc(data['breakEnd'])
        if 'present' in data:
            record.present = data['present']
        if 'notes' in data:
            record.notes = data['notes']
        if 'siteId' in data:
            record.site_id = data['siteId']

        if 'breakEnabled' in data:
            v = data['breakEnabled']
            record.break_enabled = None if v is None else bool(v)
        if 'overtimeEnabled' in data:
            v = data['overtimeEnabled']
            record.overtime_enabled = None if v is None else bool(v)

        for attr in ('checked_in', 'checked_out', 'break_start', 'break_end'):
            v = getattr(record, attr)
            if v is not None and v.tzinfo is not None:
                setattr(record, attr, v.astimezone(timezone.utc).replace(tzinfo=None))

        if record.checked_in and record.checked_out and record.checked_out < record.checked_in:
            record.checked_out = record.checked_in
        if record.break_start and record.break_end and record.break_end < record.break_start:
            record.break_end = record.break_start

        worker = Worker.query.get(record.worker_id)
        _recalc_record(record, worker)

        db.session.commit()
        return jsonify(record.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_attendance: {str(e)}")
        return jsonify({'error': str(e)}), 400


# ============================================
# PUT /attendance/<id>/edit-times
# ============================================
@attendance_bp.route('/<attendance_id>/edit-times', methods=['PUT'])
def edit_attendance_times(attendance_id):
    """
    Edit check-in/check-out/break times and/or toggle break/OT per-record.
    If the record has shifts, edits the shifts array too (if provided).
    """
    try:
        record = Attendance.query.get_or_404(attendance_id)
        data = request.json or {}

        changes = []

        if 'checkedIn' in data:
            new_in = parse_iso_utc(data['checkedIn']) if data['checkedIn'] else None
            if new_in != record.checked_in:
                record.checked_in = new_in
                changes.append('checkedIn')

        if 'checkedOut' in data:
            new_out = parse_iso_utc(data['checkedOut']) if data['checkedOut'] else None
            if new_out != record.checked_out:
                record.checked_out = new_out
                changes.append('checkedOut')

        if 'breakStart' in data:
            new_bs = parse_iso_utc(data['breakStart']) if data['breakStart'] else None
            if new_bs != record.break_start:
                record.break_start = new_bs
                changes.append('breakStart')

        if 'breakEnd' in data:
            new_be = parse_iso_utc(data['breakEnd']) if data['breakEnd'] else None
            if new_be != record.break_end:
                record.break_end = new_be
                changes.append('breakEnd')

        if 'breakEnabled' in data:
            v = data['breakEnabled']
            new_val = None if v is None else bool(v)
            if new_val != getattr(record, 'break_enabled', None):
                record.break_enabled = new_val
                changes.append('breakEnabled')

        if 'overtimeEnabled' in data:
            v = data['overtimeEnabled']
            new_val = None if v is None else bool(v)
            if new_val != getattr(record, 'overtime_enabled', None):
                record.overtime_enabled = new_val
                changes.append('overtimeEnabled')

        if 'siteId' in data:
            if data['siteId'] != record.site_id:
                record.site_id = data['siteId'] or None
                changes.append('siteId')
        if 'notes' in data:
            if data['notes'] != record.notes:
                record.notes = data['notes']
                changes.append('notes')
        if 'present' in data:
            if bool(data['present']) != bool(record.present):
                record.present = bool(data['present'])
                changes.append('present')

        for attr in ('checked_in', 'checked_out', 'break_start', 'break_end'):
            v = getattr(record, attr)
            if v is not None and v.tzinfo is not None:
                setattr(record, attr, v.astimezone(timezone.utc).replace(tzinfo=None))

        if record.checked_in and record.checked_out and record.checked_out < record.checked_in:
            return jsonify({'error': 'Check-out time cannot be earlier than check-in time'}), 400
        if record.break_start and record.break_end and record.break_end < record.break_start:
            return jsonify({'error': 'Break end time cannot be earlier than break start time'}), 400
        if record.break_start and record.checked_in and record.break_start < record.checked_in:
            return jsonify({'error': 'Break start cannot be earlier than check-in time'}), 400
        if record.break_end and record.checked_out and record.break_end > record.checked_out:
            return jsonify({'error': 'Break end cannot be later than check-out time'}), 400

        worker = Worker.query.get(record.worker_id)
        _recalc_record(record, worker)

        record.updated_at = utc_now()
        db.session.commit()
        db.session.refresh(record)

        return jsonify({
            'message': 'Attendance times updated',
            'changes': changes,
            'record': record.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error in edit_attendance_times: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400


# ============================================
# DELETE /attendance/<id>
# ============================================
@attendance_bp.route('/<attendance_id>', methods=['DELETE'])
def delete_attendance(attendance_id):
    try:
        record = Attendance.query.get_or_404(attendance_id)
        db.session.delete(record)
        db.session.commit()
        return jsonify({'message': 'Attendance record deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ============================================
# POST /attendance/checkin
# ============================================
@attendance_bp.route('/checkin', methods=['POST'])
def check_in():
    try:
        data = request.json
        worker_id = data.get('workerId')
        team_id = data.get('teamId')
        site_id = data.get('siteId')
        date_str = data.get('date')

        if not worker_id:
            return jsonify({'error': 'workerId is required'}), 400

        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else utc_now().date()

        existing = Attendance.query.filter_by(worker_id=worker_id, date=date_obj).first()
        if existing and existing.checked_in:
            return jsonify({'error': 'Worker already checked in today'}), 400

        record = Attendance(
            id=generate_id(),
            worker_id=worker_id,
            team_id=team_id,
            site_id=site_id,
            date=date_obj,
            checked_in=utc_now(),
            present=True,
            notes='Checked in via API'
        )

        if 'breakEnabled' in data:
            v = data['breakEnabled']
            record.break_enabled = None if v is None else bool(v)
        if 'overtimeEnabled' in data:
            v = data['overtimeEnabled']
            record.overtime_enabled = None if v is None else bool(v)

        db.session.add(record)
        db.session.flush()

        # ⭐ Seed the first shift on the given site
        if site_id:
            db.session.add(AttendanceShift(
                id=generate_id(),
                attendance_id=record.id,
                site_id=site_id,
                order_index=0,
                checked_in=record.checked_in,
            ))

        db.session.commit()
        return jsonify(record.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in check_in: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400


# ============================================
# PUT /attendance/<id>/checkout
# ============================================
@attendance_bp.route('/<attendance_id>/checkout', methods=['PUT'])
def check_out(attendance_id):
    try:
        record = Attendance.query.get_or_404(attendance_id)
        if record.checked_out:
            return jsonify({'error': 'Worker already checked out'}), 400

        if record.checked_in and record.checked_in.tzinfo is not None:
            record.checked_in = record.checked_in.astimezone(timezone.utc).replace(tzinfo=None)

        now = utc_now()
        if record.checked_in and now < record.checked_in:
            now = record.checked_in
        record.checked_out = now

        # ⭐ Close any open shifts too
        open_shifts = AttendanceShift.query.filter(
            AttendanceShift.attendance_id == record.id,
            AttendanceShift.checked_in.isnot(None),
            AttendanceShift.checked_out.is_(None),
        ).all()
        for sh in open_shifts:
            sh.checked_out = now

        settings = _get_settings_dict()
        if open_shifts:
            record.recalc_from_shifts(settings)
        else:
            worker = Worker.query.get(record.worker_id)
            _recalc_record(record, worker, settings)

        db.session.commit()
        return jsonify(record.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"Error in check_out: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400


# ============================================
# ⭐ MULTI-SITE SHIFTS
# ============================================
def _shift_payload(data, order_index=0):
    """Parse a shift dict from request body into AttendanceShift."""
    sh = AttendanceShift(
        id=generate_id(),
        order_index=int(data.get('orderIndex', order_index) or 0),
        site_id=data.get('siteId') or None,
        checked_in=parse_iso_utc(data.get('checkedIn')),
        checked_out=parse_iso_utc(data.get('checkedOut')),
        break_start=parse_iso_utc(data.get('breakStart')),
        break_end=parse_iso_utc(data.get('breakEnd')),
        notes=data.get('notes', ''),
    )
    if 'breakEnabled' in data:
        v = data['breakEnabled']
        sh.break_enabled = None if v is None else bool(v)
    if 'overtimeEnabled' in data:
        v = data['overtimeEnabled']
        sh.overtime_enabled = None if v is None else bool(v)
    return sh


# ⭐ CHANGED — was PUT, now GET (list) — unchanged
@attendance_bp.route('/<attendance_id>/shifts', methods=['GET'])
def list_shifts(attendance_id):
    """Return all shifts for one attendance record."""
    Attendance.query.get_or_404(attendance_id)
    shifts = AttendanceShift.query.filter_by(attendance_id=attendance_id) \
        .order_by(AttendanceShift.order_index).all()
    site_ids = {s.site_id for s in shifts if s.site_id}
    sites_map = {}
    if site_ids:
        for s in Site.query.filter(Site.id.in_(site_ids)).all():
            sites_map[s.id] = s.name
    return jsonify([sh.to_dict(site_name=sites_map.get(sh.site_id)) for sh in shifts])


# ⭐ CHANGED — was PUT at same path, now POST at same path — REPLACE SHIFTS
@attendance_bp.route('/<attendance_id>/shifts', methods=['POST'])
def replace_shifts(attendance_id):
    """
    ⭐ Bulk-replace all shifts in one shot — used by the edit modal.
    Body: { shifts: [ { siteId, checkedIn, checkedOut, breakStart, breakEnd, ... }, ... ] }

    NOTE: This route intentionally uses POST (not PUT) because PUT preflight
    requests were being rejected by CORS in some environments.
    """
    record = Attendance.query.get_or_404(attendance_id)
    data = request.json or {}
    incoming = data.get('shifts') or []

    # Remove existing
    AttendanceShift.query.filter_by(attendance_id=attendance_id).delete()

    # Add new
    for idx, item in enumerate(incoming):
        sh = _shift_payload(item, order_index=idx)
        sh.attendance_id = attendance_id
        db.session.add(sh)

    settings = _get_settings_dict()
    db.session.flush()
    record.recalc_from_shifts(settings)
    record.updated_at = utc_now()

    db.session.commit()
    db.session.refresh(record)

    return jsonify({
        'message': 'Shifts replaced',
        'record': record.to_dict(),
    })


# ⭐ CHANGED — was PUT /shifts/<shift_id>, now POST /shifts/<shift_id>/update
@attendance_bp.route('/shifts/<shift_id>/update', methods=['POST'])
def update_shift(shift_id):
    """Update one shift."""
    sh = AttendanceShift.query.get_or_404(shift_id)
    data = request.json or {}

    if 'siteId' in data:
        sh.site_id = data['siteId'] or None
    if 'checkedIn' in data:
        sh.checked_in = parse_iso_utc(data['checkedIn']) if data['checkedIn'] else None
    if 'checkedOut' in data:
        sh.checked_out = parse_iso_utc(data['checkedOut']) if data['checkedOut'] else None
    if 'breakStart' in data:
        sh.break_start = parse_iso_utc(data['breakStart']) if data['breakStart'] else None
    if 'breakEnd' in data:
        sh.break_end = parse_iso_utc(data['breakEnd']) if data['breakEnd'] else None
    if 'orderIndex' in data:
        sh.order_index = int(data['orderIndex']) if data['orderIndex'] is not None else sh.order_index
    if 'notes' in data:
        sh.notes = data['notes']
    if 'breakEnabled' in data:
        v = data['breakEnabled']
        sh.break_enabled = None if v is None else bool(v)
    if 'overtimeEnabled' in data:
        v = data['overtimeEnabled']
        sh.overtime_enabled = None if v is None else bool(v)

    for attr in ('checked_in', 'checked_out', 'break_start', 'break_end'):
        v = getattr(sh, attr)
        if v is not None and v.tzinfo is not None:
            setattr(sh, attr, v.astimezone(timezone.utc).replace(tzinfo=None))

    if sh.checked_in and sh.checked_out and sh.checked_out < sh.checked_in:
        return jsonify({'error': 'Shift check-out cannot be earlier than check-in'}), 400
    if sh.break_start and sh.break_end and sh.break_end < sh.break_start:
        return jsonify({'error': 'Shift break end cannot be earlier than break start'}), 400

    settings = _get_settings_dict()
    db.session.flush()
    record = Attendance.query.get(sh.attendance_id)
    if record:
        record.recalc_from_shifts(settings)
        record.updated_at = utc_now()

    db.session.commit()
    db.session.refresh(sh)
    if record:
        db.session.refresh(record)

    return jsonify({
        'message': 'Shift updated',
        'shift': sh.to_dict(),
        'record': record.to_dict() if record else None,
    })


# ⭐ CHANGED — was DELETE /shifts/<shift_id>, now POST /shifts/<shift_id>/delete
@attendance_bp.route('/shifts/<shift_id>/delete', methods=['POST'])
def delete_shift(shift_id):
    """Delete one shift."""
    sh = AttendanceShift.query.get_or_404(shift_id)
    record = Attendance.query.get(sh.attendance_id)
    db.session.delete(sh)

    settings = _get_settings_dict()
    db.session.flush()
    if record:
        record.recalc_from_shifts(settings)
        record.updated_at = utc_now()

    db.session.commit()
    if record:
        db.session.refresh(record)

    return jsonify({
        'message': 'Shift deleted',
        'record': record.to_dict() if record else None,
    })


# ============================================
# GET /attendance/salary-report/<month>
# ============================================
@attendance_bp.route('/salary-report/<month>', methods=['GET'])
def get_salary_report(month):
    try:
        from models.loan import EmployeeLoan
        from models.advance import EmployeeAdvance

        year, month_num = month.split('-')
        year, month_num = int(year), int(month_num)
        start, end = _month_bounds(month)
        days_in_month = monthrange(year, month_num)[1]

        settings = _get_settings_dict()
        ot_rate_cfg = float(settings.get('overtime_rate', 1.5)) or 1.5

        workers = Worker.query.filter_by(active=True).all()
        worker_ids = [w.id for w in workers]

        all_attendance = Attendance.query.filter(
            Attendance.worker_id.in_(worker_ids),
            Attendance.date >= start,
            Attendance.date <= end
        ).all()
        att_by_worker = {}
        for a in all_attendance:
            att_by_worker.setdefault(a.worker_id, []).append(a)

        all_loans = EmployeeLoan.query.filter(
            EmployeeLoan.employee_id.in_(worker_ids),
            EmployeeLoan.status == 'active'
        ).all()
        loans_by_worker = {}
        for l in all_loans:
            loans_by_worker.setdefault(l.employee_id, []).append(l)

        all_advances = EmployeeAdvance.query.filter(
            EmployeeAdvance.employee_id.in_(worker_ids),
            EmployeeAdvance.status == 'active'
        ).all()
        advances_by_worker = {}
        for a in all_advances:
            advances_by_worker.setdefault(a.employee_id, []).append(a)

        report = {
            'month': month, 'year': str(year),
            'monthName': get_month_name(month_num),
            'workers': [],
            'summary': {
                'totalWorkers': 0,
                'totalBasicSalary': 0,
                'totalOvertimeSalary': 0,
                'totalGrossSalary': 0,
                'totalLoanDeduction': 0,
                'totalAdvanceDeduction': 0,
                'totalPercentageDeduction': 0,
                'totalDeductions': 0,
                'totalNetSalary': 0,
                'totalNetPayable': 0,
            }
        }

        for worker in workers:
            attendances = att_by_worker.get(worker.id, [])
            present_days = sum(1 for a in attendances if a.present)
            total_hours = sum(max(0, float(a.total_hours or 0)) for a in attendances)
            overtime_hours = sum(max(0, float(a.overtime_hours or 0)) for a in attendances)
            normal_hours = total_hours - overtime_hours
            hourly_rate = float(worker.hourly_rate or 0)

            basic_salary = normal_hours * hourly_rate
            overtime_salary = overtime_hours * hourly_rate * ot_rate_cfg
            gross_salary = basic_salary + overtime_salary

            deduction_pct = float(getattr(worker, 'deduction_percentage', 0) or 0)
            deduction_enabled = bool(getattr(worker, 'deduction_enabled', False))
            percentage_deduction = 0.0
            if deduction_enabled and deduction_pct > 0:
                pct_clamped = max(0.0, min(100.0, deduction_pct))
                percentage_deduction = gross_salary * (pct_clamped / 100.0)

            worker_loans = loans_by_worker.get(worker.id, [])
            total_loan_deduction = sum(float(l.monthly_installment or 0) for l in worker_loans)

            worker_advances = advances_by_worker.get(worker.id, [])
            total_advance_deduction = sum(float(a.monthly_deduction or 0) for a in worker_advances)

            total_deductions = (
                percentage_deduction
                + total_loan_deduction
                + total_advance_deduction
            )
            net_salary = max(0.0, gross_salary - total_deductions)

            attendance_list = [{
                'date': a.date.isoformat() if a.date else None,
                'totalHours': max(0, float(a.total_hours or 0)),
                'overtimeHours': max(0, float(a.overtime_hours or 0)),
                'normalHours': max(0, float(a.normal_hours or 0)),
                'present': bool(a.present),
                'siteId': a.site_id,
                'breakEnabled': getattr(a, 'break_enabled', None),
                'overtimeEnabled': getattr(a, 'overtime_enabled', None),
            } for a in attendances]

            attendance_rate = (present_days / days_in_month * 100) if days_in_month else 0

            worker_report = {
                'workerId': worker.id,
                'workerName': worker.name,
                'role': worker.role or 'N/A',
                'cpr': worker.cpr if hasattr(worker, 'cpr') else None,
                'hourlyRate': hourly_rate,
                'dailyRate': float(worker.daily_rate or 0),
                'attendance': {
                    'totalDays': days_in_month,
                    'presentDays': present_days,
                    'absentDays': days_in_month - present_days,
                    'attendanceRate': attendance_rate,
                    'normalHours': normal_hours,
                    'overtimeHours': overtime_hours,
                    'totalHours': total_hours,
                    'attendances': attendance_list
                },
                'salary': {
                    'basicSalary': basic_salary,
                    'overtimeSalary': overtime_salary,
                    'grossSalary': gross_salary
                },
                'deductions': {
                    'loans': [{
                        'loanNumber': l.loan_number,
                        'amount': float(l.monthly_installment or 0),
                        'remainingBalance': float(l.remaining_balance or 0)
                    } for l in worker_loans],
                    'advances': [{
                        'advanceNumber': a.advance_number,
                        'amount': float(a.monthly_deduction or 0),
                        'remainingBalance': float(a.remaining_balance or 0)
                    } for a in worker_advances],
                    'totalLoanDeduction': total_loan_deduction,
                    'totalAdvanceDeduction': total_advance_deduction,
                    'deductionPercentage': deduction_pct,
                    'deductionEnabled': deduction_enabled,
                    'percentageDeduction': percentage_deduction,
                    'totalDeductions': total_deductions
                },
                'totalDays': days_in_month,
                'presentDays': present_days,
                'absentDays': days_in_month - present_days,
                'attendanceRate': attendance_rate,
                'totalHours': total_hours,
                'totalOvertime': overtime_hours,
                'basicHours': normal_hours,
                'basicSalary': basic_salary,
                'overtimeSalary': overtime_salary,
                'totalSalary': gross_salary,
                'loans': [{'loanNumber': l.loan_number, 'amount': float(l.monthly_installment or 0)} for l in worker_loans],
                'advances': [{'advanceNumber': a.advance_number, 'amount': float(a.monthly_deduction or 0)} for a in worker_advances],
                'totalLoanDeduction': total_loan_deduction,
                'totalAdvanceDeduction': total_advance_deduction,
                'deductionPercentage': deduction_pct,
                'deductionEnabled': deduction_enabled,
                'percentageDeduction': percentage_deduction,
                'totalDeductions': total_deductions,
                'netSalary': net_salary
            }

            report['workers'].append(worker_report)
            report['summary']['totalWorkers'] += 1
            report['summary']['totalBasicSalary'] += basic_salary
            report['summary']['totalOvertimeSalary'] += overtime_salary
            report['summary']['totalGrossSalary'] += gross_salary
            report['summary']['totalLoanDeduction'] += total_loan_deduction
            report['summary']['totalAdvanceDeduction'] += total_advance_deduction
            report['summary']['totalPercentageDeduction'] += percentage_deduction
            report['summary']['totalDeductions'] += total_deductions
            report['summary']['totalNetSalary'] += net_salary
            report['summary']['totalNetPayable'] += net_salary

        return jsonify(report), 200

    except Exception as e:
        print(f"Error in get_salary_report: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================
# GET /attendance/settings
# ============================================
@attendance_bp.route('/settings', methods=['GET'])
def get_attendance_settings():
    try:
        s = AttendanceSettings.get_settings()
        return jsonify(s.to_dict())
    except Exception as e:
        print(f"Error in get_attendance_settings: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================
# PUT /attendance/settings
# ============================================
@attendance_bp.route('/settings', methods=['PUT'])
def update_attendance_settings():
    try:
        s = AttendanceSettings.get_settings()
        data = request.json or {}

        if 'shiftStartTime' in data:  s.shift_start_time = str(data['shiftStartTime'])[:5]
        if 'shiftEndTime' in data:    s.shift_end_time   = str(data['shiftEndTime'])[:5]
        if 'shiftHours' in data:      s.shift_hours      = max(0.0, float(data['shiftHours']))
        if 'breakStartTime' in data:  s.break_start_time = str(data['breakStartTime'])[:5]
        if 'breakEndTime' in data:    s.break_end_time   = str(data['breakEndTime'])[:5]
        if 'breakHours' in data:      s.break_hours      = max(0.0, float(data['breakHours']))
        if 'breakEnabled' in data:    s.break_enabled    = bool(data['breakEnabled'])

        if 'overtimeRate' in data:    s.overtime_rate    = max(1.0, float(data['overtimeRate']))
        if 'overtimeEnabled' in data: s.overtime_enabled = bool(data['overtimeEnabled'])

        if 'earlyInThreshold' in data:  s.early_in_threshold  = max(0, int(data['earlyInThreshold']))
        if 'lateInThreshold' in data:   s.late_in_threshold   = max(0, int(data['lateInThreshold']))
        if 'earlyOutThreshold' in data: s.early_out_threshold = max(0, int(data['earlyOutThreshold']))
        if 'lateOutThreshold' in data:  s.late_out_threshold  = max(0, int(data['lateOutThreshold']))

        if 'countEarlyIn' in data:  s.count_early_in  = bool(data['countEarlyIn'])
        if 'countLateIn' in data:   s.count_late_in   = bool(data['countLateIn'])
        if 'countEarlyOut' in data: s.count_early_out = bool(data['countEarlyOut'])
        if 'countLateOut' in data:  s.count_late_out  = bool(data['countLateOut'])

        db.session.commit()
        return jsonify({'message': 'Settings updated', 'settings': s.to_dict()})
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_attendance_settings: {str(e)}")
        return jsonify({'error': str(e)}), 400


# ============================================
# HELPERS
# ============================================
def get_month_name(month_num):
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    return months[month_num - 1] if 1 <= month_num <= 12 else 'Unknown'


def get_days_in_month(year, month_num):
    return monthrange(int(year), month_num)[1]


def get_last_day(year, month_num):
    return str(get_days_in_month(year, month_num)).zfill(2)