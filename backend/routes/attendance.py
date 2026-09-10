# routes/attendance.py
from flask import request, jsonify
from datetime import datetime, timedelta
from models import db, Attendance, Worker, WorkerTeam, TeamMember, Site
from utils.helpers import generate_id
from routes import attendance_bp
from sqlalchemy import func, and_


@attendance_bp.route('', methods=['GET'])
def get_attendance():
    """Get all attendance records with optional filters"""
    try:
        date = request.args.get('date')
        worker_id = request.args.get('workerId')
        team_id = request.args.get('teamId')
        site_id = request.args.get('siteId')
        month = request.args.get('month')

        query = Attendance.query
        if date:
            query = query.filter_by(date=datetime.strptime(date, '%Y-%m-%d').date())
        if worker_id:
            query = query.filter_by(worker_id=worker_id)
        if team_id:
            query = query.filter_by(team_id=team_id)
        if site_id:
            query = query.filter_by(site_id=site_id)
        if month:
            query = query.filter(Attendance.date.like(f'{month}%'))

        records = query.order_by(Attendance.date.desc(), Attendance.created_at.desc()).all()

        # Preload sites referenced by these records so we can include site names
        site_ids = list({r.site_id for r in records if r.site_id})
        sites_map = {}
        if site_ids:
            sites = Site.query.filter(Site.id.in_(site_ids)).all()
            sites_map = {s.id: s.name for s in sites}

        result = []
        for r in records:
            d = r.to_dict()
            d['siteName'] = sites_map.get(r.site_id) if r.site_id else None
            result.append(d)
        return jsonify(result)
    except Exception as e:
        print(f"Error in get_attendance: {str(e)}")
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/team/<team_id>', methods=['GET'])
def get_team_attendance(team_id):
    """Get attendance for all members of a team on a specific date"""
    try:
        date = request.args.get('date')
        if not date:
            return jsonify({'error': 'Date parameter is required'}), 400

        # Get all workers in the team
        team_members = TeamMember.query.filter_by(team_id=team_id).all()
        worker_ids = [tm.worker_id for tm in team_members]

        if not worker_ids:
            return jsonify({
                'team_id': team_id,
                'date': date,
                'members': [],
                'stats': {
                    'total_members': 0,
                    'present': 0,
                    'absent': 0,
                    'total_hours': 0,
                    'total_wages': 0,
                    'attendance_rate': 0
                }
            })

        # Get attendance records for these workers on the given date
        attendance_records = Attendance.query.filter(
            Attendance.worker_id.in_(worker_ids),
            Attendance.date == datetime.strptime(date, '%Y-%m-%d').date()
        ).all()

        # Get worker details
        workers = Worker.query.filter(Worker.id.in_(worker_ids)).all()

        # Preload sites referenced by attendance records
        site_ids = list({r.site_id for r in attendance_records if r.site_id})
        sites_map = {}
        if site_ids:
            sites = Site.query.filter(Site.id.in_(site_ids)).all()
            sites_map = {s.id: s.name for s in sites}

        result = []
        for worker in workers:
            record = next((r for r in attendance_records if r.worker_id == worker.id), None)
            result.append({
                'worker': worker.to_dict(),
                'attendance': record.to_dict() if record else None,
                'present': record.present if record else False,
                'checkedIn': record.checked_in.isoformat() if record and record.checked_in else None,
                'checkedOut': record.checked_out.isoformat() if record and record.checked_out else None,
                'hoursWorked': float(record.total_hours) if record and record.total_hours else 0,
                'wageEarned': float(record.wage_earned) if record and record.wage_earned else 0,
                'siteId': record.site_id if record else None,
                'siteName': sites_map.get(record.site_id) if record and record.site_id else None,
            })

        # Calculate team stats
        total_present = sum(1 for r in result if r['present'])
        total_hours = sum(r['hoursWorked'] for r in result)
        total_wages = sum(r['wageEarned'] for r in result)

        return jsonify({
            'team_id': team_id,
            'date': date,
            'members': result,
            'stats': {
                'total_members': len(result),
                'present': total_present,
                'absent': len(result) - total_present,
                'total_hours': total_hours,
                'total_wages': total_wages,
                'attendance_rate': (total_present / len(result) * 100) if len(result) > 0 else 0
            }
        })
    except Exception as e:
        print(f"Error in get_team_attendance: {str(e)}")
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('/team/<team_id>/checkin-all', methods=['POST'])
def check_in_all_team(team_id):
    """Check in all members of a team who are not already checked in"""
    try:
        data = request.json or {}
        date_str = data.get('date', datetime.now().date().isoformat())
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        site_id = data.get('siteId')

        print(f"📊 Checking in all team members for team {team_id} on {date_str} (site={site_id})")

        # Get all workers in the team
        team_members = TeamMember.query.filter_by(team_id=team_id).all()
        worker_ids = [tm.worker_id for tm in team_members]

        if not worker_ids:
            return jsonify({
                'message': 'No members in this team',
                'checked_in': 0,
                'already_checked_in': 0,
                'total': 0
            })

        # Get existing attendance for that date
        existing = Attendance.query.filter(
            Attendance.worker_id.in_(worker_ids),
            Attendance.date == date_obj
        ).all()

        existing_worker_ids = [r.worker_id for r in existing if r.checked_in is not None]

        # Create attendance for workers who don't have it yet
        created = []
        for worker_id in worker_ids:
            if worker_id not in existing_worker_ids:
                record = Attendance(
                    id=generate_id(),
                    worker_id=worker_id,
                    team_id=team_id,
                    site_id=site_id,
                    date=date_obj,
                    checked_in=datetime.now(),
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


@attendance_bp.route('/team/<team_id>/checkout-all', methods=['POST'])
def check_out_all_team(team_id):
    """Check out all members of a team who are currently checked in"""
    try:
        data = request.json or {}
        date_str = data.get('date', datetime.now().date().isoformat())
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        print(f"📊 Checking out all team members for team {team_id} on {date_str}")

        # Get all workers in the team
        team_members = TeamMember.query.filter_by(team_id=team_id).all()
        worker_ids = [tm.worker_id for tm in team_members]

        if not worker_ids:
            return jsonify({
                'message': 'No members in this team',
                'checked_out': 0,
                'total_hours': 0,
                'total_wages': 0
            })

        # Get attendance records for that date that are checked in but not checked out
        records = Attendance.query.filter(
            Attendance.worker_id.in_(worker_ids),
            Attendance.date == date_obj,
            Attendance.checked_in.isnot(None),
            Attendance.checked_out.is_(None)
        ).all()

        checked_out = []
        for record in records:
            record.checked_out = datetime.now()
            record.calculate_hours()

            # Calculate wage
            worker = Worker.query.get(record.worker_id)
            if worker:
                record.wage_earned = record.calculate_wage()

            checked_out.append(record)

        db.session.commit()

        total_hours = sum(r.total_hours or 0 for r in checked_out)
        total_wages = sum(r.wage_earned or 0 for r in checked_out)

        return jsonify({
            'message': f'Checked out {len(checked_out)} team members',
            'checked_out': len(checked_out),
            'total_hours': total_hours,
            'total_wages': total_wages
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error in check_out_all_team: {str(e)}")
        return jsonify({'error': str(e)}), 400


@attendance_bp.route('/team-summary/<team_id>', methods=['GET'])
def get_team_attendance_summary(team_id):
    """Get attendance summary for a team over a date range"""
    try:
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        month = request.args.get('month')

        if month:
            start_date = f"{month}-01"
            year, month_num = month.split('-')
            last_day = 31
            try:
                from calendar import monthrange
                last_day = monthrange(int(year), int(month_num))[1]
            except:
                pass
            end_date = f"{month}-{last_day:02d}"

        if not start_date or not end_date:
            return jsonify({'error': 'Start date and end date are required'}), 400

        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        # Get all workers in the team
        team_members = TeamMember.query.filter_by(team_id=team_id).all()
        worker_ids = [tm.worker_id for tm in team_members]

        if not worker_ids:
            return jsonify({
                'team_id': team_id,
                'start_date': start_date,
                'end_date': end_date,
                'total_days': 0,
                'total_workers': 0,
                'total_possible_attendance': 0,
                'total_present_days': 0,
                'total_hours': 0,
                'total_wages': 0,
                'overall_attendance_rate': 0,
                'worker_summary': []
            })

        # Get attendance records for date range
        records = Attendance.query.filter(
            Attendance.worker_id.in_(worker_ids),
            Attendance.date >= start,
            Attendance.date <= end
        ).all()

        # Calculate summary
        total_days = (end - start).days + 1
        total_workers = len(worker_ids)
        total_possible = total_days * total_workers

        present_days = sum(1 for r in records if r.present)
        total_hours = sum(r.total_hours or 0 for r in records)
        total_wages = sum(r.wage_earned or 0 for r in records)

        # Per worker summary
        worker_summary = []
        for worker_id in worker_ids:
            worker_records = [r for r in records if r.worker_id == worker_id]
            worker = Worker.query.get(worker_id)
            if worker:
                worker_summary.append({
                    'worker_id': worker_id,
                    'worker_name': worker.name,
                    'total_present': sum(1 for r in worker_records if r.present),
                    'total_absent': total_days - sum(1 for r in worker_records if r.present),
                    'total_hours': sum(r.total_hours or 0 for r in worker_records),
                    'total_wages': sum(r.wage_earned or 0 for r in worker_records),
                    'attendance_rate': (sum(1 for r in worker_records if r.present) / total_days * 100) if total_days > 0 else 0
                })

        return jsonify({
            'team_id': team_id,
            'start_date': start_date,
            'end_date': end_date,
            'total_days': total_days,
            'total_workers': total_workers,
            'total_possible_attendance': total_possible,
            'total_present_days': present_days,
            'total_hours': total_hours,
            'total_wages': total_wages,
            'overall_attendance_rate': (present_days / total_possible * 100) if total_possible > 0 else 0,
            'worker_summary': worker_summary
        })
    except Exception as e:
        print(f"Error in get_team_attendance_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500


@attendance_bp.route('', methods=['POST'])
def create_attendance():
    """Create a new attendance record"""
    try:
        data = request.json

        checked_in = None
        checked_out = None

        if data.get('checkedIn'):
            checked_in = datetime.fromisoformat(data.get('checkedIn').replace('Z', '+00:00'))
        if data.get('checkedOut'):
            checked_out = datetime.fromisoformat(data.get('checkedOut').replace('Z', '+00:00'))

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


@attendance_bp.route('/<attendance_id>', methods=['GET'])
def get_attendance_record(attendance_id):
    """Get a specific attendance record"""
    try:
        record = Attendance.query.get_or_404(attendance_id)
        return jsonify(record.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@attendance_bp.route('/<attendance_id>', methods=['PUT'])
def update_attendance(attendance_id):
    try:
        record = Attendance.query.get_or_404(attendance_id)
        data = request.json

        if 'checkedIn' in data and data['checkedIn']:
            record.checked_in = datetime.fromisoformat(data['checkedIn'].replace('Z', '+00:00'))
        if 'checkedOut' in data and data['checkedOut']:
            record.checked_out = datetime.fromisoformat(data['checkedOut'].replace('Z', '+00:00'))
        if 'present' in data:
            record.present = data['present']
        if 'notes' in data:
            record.notes = data['notes']
        if 'siteId' in data:
            record.site_id = data['siteId']

        # Recalculate hours + wage whenever either timestamp changed
        if record.checked_in and record.checked_out:
            record.calculate_hours()
            worker = Worker.query.get(record.worker_id)
            if worker:
                record.wage_earned = record.calculate_wage()

        db.session.commit()
        return jsonify(record.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_attendance: {str(e)}")
        return jsonify({'error': str(e)}), 400

@attendance_bp.route('/<attendance_id>', methods=['DELETE'])
def delete_attendance(attendance_id):
    """Delete an attendance record"""
    try:
        record = Attendance.query.get_or_404(attendance_id)
        db.session.delete(record)
        db.session.commit()
        return jsonify({'message': 'Attendance record deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@attendance_bp.route('/checkin', methods=['POST'])
def check_in():
    """Check in a worker"""
    try:
        data = request.json
        worker_id = data.get('workerId')
        team_id = data.get('teamId')
        site_id = data.get('siteId')
        date_str = data.get('date')

        if not worker_id:
            return jsonify({'error': 'workerId is required'}), 400

        # Determine date
        if date_str:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date_obj = datetime.now().date()

        # Check if already checked in that day
        existing = Attendance.query.filter_by(
            worker_id=worker_id,
            date=date_obj
        ).first()

        if existing and existing.checked_in:
            return jsonify({'error': 'Worker already checked in today'}), 400

        record = Attendance(
            id=generate_id(),
            worker_id=worker_id,
            team_id=team_id,
            site_id=site_id,
            date=date_obj,
            checked_in=datetime.now(),
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


@attendance_bp.route('/<attendance_id>/checkout', methods=['PUT'])
def check_out(attendance_id):
    try:
        record = Attendance.query.get_or_404(attendance_id)
        if record.checked_out:
            return jsonify({'error': 'Worker already checked out'}), 400

        record.checked_out = datetime.now()
        record.calculate_hours()

        worker = Worker.query.get(record.worker_id)
        if worker:
            record.wage_earned = record.calculate_wage()   # ← was missing or broken

        db.session.commit()
        return jsonify(record.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"Error in check_out: {str(e)}")
        return jsonify({'error': str(e)}), 400

@attendance_bp.route('/salary-report/<month>', methods=['GET'])
def get_salary_report(month):
    """
    Get complete salary report for a month including:
    - Attendance
    - Basic Salary
    - Overtime
    - Loan Deductions
    - Advance Deductions
    - Net Salary
    """
    try:
        from models.loan import EmployeeLoan
        from models.advance import EmployeeAdvance

        # Parse month
        year, month_num = month.split('-')
        month_num = int(month_num)

        # Get all workers
        workers = Worker.query.filter_by(active=True).all()

        report = {
            'month': month,
            'year': year,
            'monthName': get_month_name(month_num),
            'workers': [],
            'summary': {
                'totalWorkers': 0,
                'totalBasicSalary': 0,
                'totalOvertimeSalary': 0,
                'totalGrossSalary': 0,
                'totalLoanDeduction': 0,
                'totalAdvanceDeduction': 0,
                'totalDeductions': 0,
                'totalNetSalary': 0
            }
        }

        for worker in workers:
            # Get attendance for the month
            attendances = Attendance.query.filter(
                Attendance.worker_id == worker.id,
                Attendance.date >= f'{month}-01',
                Attendance.date <= f'{month}-{get_last_day(year, month_num)}'
            ).all()

            # Calculate attendance stats
            present_days = sum(1 for a in attendances if a.present)
            total_hours = sum(float(a.total_hours or 0) for a in attendances)
            overtime_hours = sum(float(a.overtime_hours or 0) for a in attendances)
            normal_hours = total_hours - overtime_hours

            # Calculate salary
            hourly_rate = float(worker.hourly_rate or 0)
            basic_salary = normal_hours * hourly_rate
            overtime_salary = overtime_hours * hourly_rate * 1.5
            gross_salary = basic_salary + overtime_salary

            # Get active loans for this worker
            active_loans = EmployeeLoan.query.filter_by(
                employee_id=worker.id,
                status='active'
            ).all()
            total_loan_deduction = sum(float(loan.monthly_installment or 0) for loan in active_loans)

            # Get active advances for this worker
            active_advances = EmployeeAdvance.query.filter_by(
                employee_id=worker.id,
                status='active'
            ).all()
            total_advance_deduction = sum(float(advance.monthly_deduction or 0) for advance in active_advances)

            total_deductions = total_loan_deduction + total_advance_deduction
            net_salary = gross_salary - total_deductions

            # Build per-attendance list for the salary slip's daily breakdown
            attendance_list = []
            for a in attendances:
                attendance_list.append({
                    'date': a.date.isoformat() if a.date else None,
                    'totalHours': float(a.total_hours or 0),
                    'overtimeHours': float(a.overtime_hours or 0),
                    'present': bool(a.present),
                    'siteId': a.site_id,
                })

            worker_report = {
                'workerId': worker.id,
                'workerName': worker.name,
                'role': worker.role or 'N/A',
                'cpr': worker.cpr if hasattr(worker, 'cpr') else None,
                'hourlyRate': hourly_rate,
                'dailyRate': float(worker.daily_rate or 0),
                'attendance': {
                    'totalDays': get_days_in_month(year, month_num),
                    'presentDays': present_days,
                    'absentDays': get_days_in_month(year, month_num) - present_days,
                    'attendanceRate': (present_days / get_days_in_month(year, month_num) * 100) if get_days_in_month(year, month_num) > 0 else 0,
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
                    'loans': [
                        {
                            'loanNumber': loan.loan_number,
                            'amount': float(loan.monthly_installment or 0),
                            'remainingBalance': float(loan.remaining_balance or 0)
                        } for loan in active_loans
                    ],
                    'advances': [
                        {
                            'advanceNumber': advance.advance_number,
                            'amount': float(advance.monthly_deduction or 0),
                            'remainingBalance': float(advance.remaining_balance or 0)
                        } for advance in active_advances
                    ],
                    'totalLoanDeduction': total_loan_deduction,
                    'totalAdvanceDeduction': total_advance_deduction,
                    'totalDeductions': total_deductions
                },
                # Flat convenience fields for the frontend salary slip generator
                'totalDays': get_days_in_month(year, month_num),
                'presentDays': present_days,
                'absentDays': get_days_in_month(year, month_num) - present_days,
                'attendanceRate': (present_days / get_days_in_month(year, month_num) * 100) if get_days_in_month(year, month_num) > 0 else 0,
                'totalHours': total_hours,
                'totalOvertime': overtime_hours,
                'basicHours': normal_hours,
                'basicSalary': basic_salary,
                'overtimeSalary': overtime_salary,
                'totalSalary': gross_salary,
                'loans': [
                    {
                        'loanNumber': loan.loan_number,
                        'amount': float(loan.monthly_installment or 0),
                    } for loan in active_loans
                ],
                'advances': [
                    {
                        'advanceNumber': advance.advance_number,
                        'amount': float(advance.monthly_deduction or 0),
                    } for advance in active_advances
                ],
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
    """Get month name from number"""
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    return months[month_num - 1] if 1 <= month_num <= 12 else 'Unknown'


def get_days_in_month(year, month_num):
    """Get number of days in a month"""
    from calendar import monthrange
    return monthrange(int(year), month_num)[1]


def get_last_day(year, month_num):
    """Get last day of month"""
    return str(get_days_in_month(year, month_num)).zfill(2)