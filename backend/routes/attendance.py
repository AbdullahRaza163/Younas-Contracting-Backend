# routes/attendance.py
from flask import request, jsonify
from datetime import datetime, timedelta, timezone
from calendar import monthrange
from models import db, Attendance, Worker, WorkerTeam, TeamMember, Site
from utils.helpers import generate_id
from routes import attendance_bp
from sqlalchemy import func, and_


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
        month      = request.args.get('month')       # 'YYYY-MM'
        start_date = request.args.get('startDate')
        end_date   = request.args.get('endDate')

        query = Attendance.query

        if date:
            query = query.filter(Attendance.date == datetime.strptime(date, '%Y-%m-%d').date())
        if worker_id:
            query = query.filter(Attendance.worker_id == worker_id)
        if team_id:
            query = query.filter(Attendance.team_id == team_id)
        if site_id:
            query = query.filter(Attendance.site_id == site_id)

        # ⭐ Range comparison — the index-friendly way (LIKE doesn't work on DATE)
        if month:
            start, end = _month_bounds(month)
            query = query.filter(Attendance.date >= start, Attendance.date <= end)
        elif start_date or end_date:
            if start_date:
                query = query.filter(Attendance.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
            if end_date:
                query = query.filter(Attendance.date <= datetime.strptime(end_date, '%Y-%m-%d').date())

        records = query.order_by(Attendance.date.desc(), Attendance.created_at.desc()).all()

        # Preload sites + workers to avoid N+1
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
        sites_map = {}
        if site_ids:
            sites = Site.query.filter(Site.id.in_(site_ids)).all()
            sites_map = {s.id: s.name for s in sites}

        # Group once — O(n)
        att_by_worker = {r.worker_id: r for r in attendance_records}

        result = []
        for worker in workers:
            record = att_by_worker.get(worker.id)
            hours = float(record.total_hours or 0) if record else 0
            if hours < 0:
                hours = 0
            result.append({
                'worker': worker.to_dict(),
                'attendance': record.to_dict() if record else None,
                'present': bool(record.present) if record else False,
                'checkedIn': record.checked_in.isoformat() if record and record.checked_in else None,
                'checkedOut': record.checked_out.isoformat() if record and record.checked_out else None,
                'hoursWorked': hours,
                'wageEarned': float(record.wage_earned or 0) if record else 0,
                'overtimeHours': float(record.overtime_hours or 0) if record else 0,
                'siteId': record.site_id if record else None,
                'siteName': sites_map.get(record.site_id) if record and record.site_id else None,
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

        now = utc_now()
        for record in records:
            # ⭐ Normalize checked_in before arithmetic
            if record.checked_in and record.checked_in.tzinfo is not None:
                record.checked_in = record.checked_in.astimezone(timezone.utc).replace(tzinfo=None)

            checkout_time = now
            if record.checked_in and checkout_time < record.checked_in:
                checkout_time = record.checked_in
            record.checked_out = checkout_time
            record.calculate_hours()

            if record.total_hours is not None and record.total_hours < 0:
                record.total_hours = 0.0
                record.normal_hours = 0.0
                record.overtime_hours = 0.0

            w = workers_map.get(record.worker_id)
            if w:
                base = (record.normal_hours or 0) * w.hourly_rate
                ot = (record.overtime_hours or 0) * w.hourly_rate * 1.5
                record.wage_earned = round(base + ot, 2)

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

        # Group once — O(n)
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

        if checked_in and checked_out:
            record.calculate_hours()
            if record.total_hours is not None and record.total_hours < 0:
                record.total_hours = 0.0
                record.normal_hours = 0.0
                record.overtime_hours = 0.0
            worker = Worker.query.get(data.get('workerId'))
            if worker:
                record.wage_earned = record.calculate_wage()

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
# PUT /attendance/<id>
# ============================================
@attendance_bp.route('/<attendance_id>', methods=['PUT'])
def update_attendance(attendance_id):
    try:
        record = Attendance.query.get_or_404(attendance_id)
        data = request.json

        if 'checkedIn' in data and data['checkedIn']:
            record.checked_in = parse_iso_utc(data['checkedIn'])
        if 'checkedOut' in data and data['checkedOut']:
            record.checked_out = parse_iso_utc(data['checkedOut'])
        if 'present' in data:
            record.present = data['present']
        if 'notes' in data:
            record.notes = data['notes']
        if 'siteId' in data:
            record.site_id = data['siteId']

        # ⭐ Normalize any aware datetimes that snuck in
        if record.checked_in and record.checked_in.tzinfo is not None:
            record.checked_in = record.checked_in.astimezone(timezone.utc).replace(tzinfo=None)
        if record.checked_out and record.checked_out.tzinfo is not None:
            record.checked_out = record.checked_out.astimezone(timezone.utc).replace(tzinfo=None)

        if record.checked_in and record.checked_out:
            record.calculate_hours()
            if record.total_hours is not None and record.total_hours < 0:
                record.total_hours = 0.0
                record.normal_hours = 0.0
                record.overtime_hours = 0.0
            worker = Worker.query.get(record.worker_id)
            if worker:
                record.wage_earned = record.calculate_wage()

        db.session.commit()
        return jsonify(record.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_attendance: {str(e)}")
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
        db.session.add(record)
        db.session.commit()
        return jsonify(record.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in check_in: {str(e)}")
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

        # ⭐ Normalize checked_in if aware
        if record.checked_in and record.checked_in.tzinfo is not None:
            record.checked_in = record.checked_in.astimezone(timezone.utc).replace(tzinfo=None)

        now = utc_now()
        if record.checked_in and now < record.checked_in:
            now = record.checked_in
        record.checked_out = now
        record.calculate_hours()

        if record.total_hours is not None and record.total_hours < 0:
            record.total_hours = 0.0
            record.normal_hours = 0.0
            record.overtime_hours = 0.0

        worker = Worker.query.get(record.worker_id)
        if worker:
            record.wage_earned = record.calculate_wage()

        db.session.commit()
        return jsonify(record.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"Error in check_out: {str(e)}")
        return jsonify({'error': str(e)}), 400


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
                'totalWorkers': 0, 'totalBasicSalary': 0, 'totalOvertimeSalary': 0,
                'totalGrossSalary': 0, 'totalLoanDeduction': 0,
                'totalAdvanceDeduction': 0, 'totalDeductions': 0, 'totalNetSalary': 0
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
            overtime_salary = overtime_hours * hourly_rate * 1.5
            gross_salary = basic_salary + overtime_salary

            worker_loans = loans_by_worker.get(worker.id, [])
            total_loan_deduction = sum(float(l.monthly_installment or 0) for l in worker_loans)

            worker_advances = advances_by_worker.get(worker.id, [])
            total_advance_deduction = sum(float(a.monthly_deduction or 0) for a in worker_advances)

            total_deductions = total_loan_deduction + total_advance_deduction
            net_salary = gross_salary - total_deductions

            attendance_list = [{
                'date': a.date.isoformat() if a.date else None,
                'totalHours': max(0, float(a.total_hours or 0)),
                'overtimeHours': max(0, float(a.overtime_hours or 0)),
                'present': bool(a.present),
                'siteId': a.site_id,
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
            report['summary']['totalDeductions'] += total_deductions
            report['summary']['totalNetSalary'] += net_salary

        return jsonify(report), 200

    except Exception as e:
        print(f"Error in get_salary_report: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def get_month_name(month_num):
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    return months[month_num - 1] if 1 <= month_num <= 12 else 'Unknown'


def get_days_in_month(year, month_num):
    return monthrange(int(year), month_num)[1]


def get_last_day(year, month_num):
    return str(get_days_in_month(year, month_num)).zfill(2)