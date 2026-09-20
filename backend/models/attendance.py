# models/attendance.py
from models import db
from datetime import datetime, timezone


class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.String(20), primary_key=True)
    worker_id = db.Column(db.String(20), db.ForeignKey('workers.id', ondelete='CASCADE'), nullable=False)
    team_id = db.Column(db.String(20), db.ForeignKey('worker_teams.id', ondelete='SET NULL'))
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='SET NULL'))
    date = db.Column(db.Date, nullable=False)
    checked_in = db.Column(db.DateTime)
    checked_out = db.Column(db.DateTime)
    break_start = db.Column(db.DateTime)
    break_end = db.Column(db.DateTime)
    present = db.Column(db.Boolean, default=False)

    # ⭐ Per-record toggles. NULL means "use global setting".
    break_enabled = db.Column(db.Boolean, nullable=True, default=None)
    overtime_enabled = db.Column(db.Boolean, nullable=True, default=None)

    overtime_hours = db.Column(db.Float, default=0.0)
    normal_hours = db.Column(db.Float, default=0.0)
    total_hours = db.Column(db.Float, default=0.0)
    wage_earned = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    worker = db.relationship('Worker', backref='attendance_records', foreign_keys=[worker_id])

    # ⭐ Accepts site_name / worker_name from the caller to avoid N+1 queries
    def to_dict(self, site_name=None, worker_name=None):
        return {
            'id': self.id,
            'workerId': self.worker_id,
            'workerName': worker_name if worker_name is not None
                          else (self.worker.name if self.worker else None),
            'teamId': self.team_id,
            'siteId': self.site_id,
            'siteName': site_name,
            'date': self.date.isoformat() if self.date else None,
            'checkedIn': self.checked_in.isoformat() if self.checked_in else None,
            'checkedOut': self.checked_out.isoformat() if self.checked_out else None,
            'breakStart': self.break_start.isoformat() if self.break_start else None,
            'breakEnd': self.break_end.isoformat() if self.break_end else None,
            'present': self.present,
            # ⭐ null means inherit global setting
            'breakEnabled': self.break_enabled,
            'overtimeEnabled': self.overtime_enabled,
            'overtimeHours': self.overtime_hours,
            'normalHours': self.normal_hours,
            'totalHours': self.total_hours,
            'wageEarned': self.wage_earned,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }

    # ───────── Settings helpers ─────────
    @staticmethod
    def _load_settings():
        """
        Load attendance settings from DB.
        Returns a dict with safe defaults so calculate_hours/calculate_wage
        never blow up if settings are missing.
        """
        defaults = {
            'shift_hours': 8.0,
            'break_enabled': True,
            'break_hours': 1.0,
            'break_start_time': None,
            'break_end_time': None,
            'overtime_enabled': True,
            'overtime_rate': 1.5,
        }
        try:
            from models.attendance_settings import AttendanceSettings
            # ⭐ get_settings() auto-creates the row if it doesn't exist
            s = AttendanceSettings.get_settings() if hasattr(AttendanceSettings, 'get_settings') \
                else AttendanceSettings.query.first()
            if not s:
                return defaults
            return {
                'shift_hours': float(getattr(s, 'shift_hours', None) or defaults['shift_hours']),
                'break_enabled': bool(getattr(s, 'break_enabled', defaults['break_enabled'])),
                'break_hours': float(getattr(s, 'break_hours', None) or 0),
                'break_start_time': getattr(s, 'break_start_time', None),
                'break_end_time': getattr(s, 'break_end_time', None),
                'overtime_enabled': bool(getattr(s, 'overtime_enabled', defaults['overtime_enabled'])),
                'overtime_rate': float(getattr(s, 'overtime_rate', None) or defaults['overtime_rate']),
            }
        except Exception as e:
            print(f"[Attendance._load_settings] falling back to defaults: {e}")
            return defaults

    def _resolve_break_enabled(self, settings=None):
        """Per-record override → global setting. Default: True."""
        if self.break_enabled is not None:
            return bool(self.break_enabled)
        if settings is None:
            settings = self._load_settings()
        return bool(settings.get('break_enabled', True))

    def _resolve_overtime_enabled(self, settings=None):
        """Per-record override → global setting. Default: True."""
        if self.overtime_enabled is not None:
            return bool(self.overtime_enabled)
        if settings is None:
            settings = self._load_settings()
        return bool(settings.get('overtime_enabled', True))

    # ───────── Calculations ─────────
    def calculate_hours(self, settings=None):
        """
        Calculate normal and overtime hours.
        - Respects break_enabled (per-record → global).
        - Respects overtime_enabled (per-record → global).
        - Robust against mixed naive/aware datetimes.
        - Never returns negative values.
        """
        if not self.checked_in or not self.checked_out:
            return

        if settings is None:
            settings = self._load_settings()

        checked_in = self.checked_in
        checked_out = self.checked_out

        # Normalize both to naive UTC
        if checked_in.tzinfo is not None:
            checked_in = checked_in.astimezone(timezone.utc).replace(tzinfo=None)
        if checked_out.tzinfo is not None:
            checked_out = checked_out.astimezone(timezone.utc).replace(tzinfo=None)

        total_seconds = (checked_out - checked_in).total_seconds()

        # Clamp negative (mixed timezones / bad data)
        if total_seconds < 0:
            self.total_hours = 0.0
            self.normal_hours = 0.0
            self.overtime_hours = 0.0
            return

        # ⭐ Break subtraction — ONLY if break is enabled
        break_enabled = self._resolve_break_enabled(settings)
        if break_enabled and self.break_start and self.break_end:
            bs = self.break_start
            be = self.break_end
            if bs.tzinfo is not None:
                bs = bs.astimezone(timezone.utc).replace(tzinfo=None)
            if be.tzinfo is not None:
                be = be.astimezone(timezone.utc).replace(tzinfo=None)
            break_seconds = (be - bs).total_seconds()
            if break_seconds > 0:
                total_seconds -= break_seconds

        total_hours = max(0.0, total_seconds / 3600)
        self.total_hours = round(total_hours, 2)

        # ⭐ OT split — respects OT toggle & configured shift hours
        overtime_enabled = self._resolve_overtime_enabled(settings)
        shift_hours = float(settings.get('shift_hours', 8.0)) or 8.0

        if overtime_enabled and total_hours > shift_hours:
            self.normal_hours = round(shift_hours, 2)
            self.overtime_hours = round(total_hours - shift_hours, 2)
        else:
            # OT disabled → everything is normal hours
            self.normal_hours = round(total_hours, 2)
            self.overtime_hours = 0.0

    def calculate_wage(self, settings=None):
        """
        Calculate wage earned based on worker's hourly rate.
        - Respects overtime_enabled (per-record → global).
        - Uses overtime_rate from settings (not hardcoded 1.5).
        - Never negative.
        """
        if settings is None:
            settings = self._load_settings()

        if self.worker:
            # Prefer worker.hourly_rate; fall back to daily_rate / shift_hours
            hourly_rate = float(getattr(self.worker, 'hourly_rate', 0) or 0)
            if not hourly_rate:
                daily_rate = float(getattr(self.worker, 'daily_rate', 0) or 0)
                shift_hours = float(settings.get('shift_hours', 8.0)) or 8.0
                if daily_rate and shift_hours:
                    hourly_rate = daily_rate / shift_hours

            normal = max(0.0, self.normal_hours or 0.0)
            overtime = max(0.0, self.overtime_hours or 0.0)

            base_wage = normal * hourly_rate

            overtime_enabled = self._resolve_overtime_enabled(settings)
            ot_rate = float(settings.get('overtime_rate', 1.5)) or 1.5
            if overtime_enabled:
                overtime_wage = overtime * hourly_rate * ot_rate
            else:
                # OT disabled → OT hours paid at normal rate
                overtime_wage = overtime * hourly_rate

            self.wage_earned = round(max(0.0, base_wage + overtime_wage), 2)

        return self.wage_earned

    # ───────── Clock in / out ─────────
    def check_in(self, time=None):
        """Check in the worker. Always stores a naive UTC datetime."""
        t = time or datetime.utcnow()
        if t.tzinfo is not None:
            t = t.astimezone(timezone.utc).replace(tzinfo=None)
        self.checked_in = t
        self.present = True

    def check_out(self, time=None):
        """Check out the worker. Always stores a naive UTC datetime."""
        t = time or datetime.utcnow()
        if t.tzinfo is not None:
            t = t.astimezone(timezone.utc).replace(tzinfo=None)
        # Guard: never earlier than checked_in
        if self.checked_in and t < self.checked_in:
            t = self.checked_in
        self.checked_out = t
        settings = self._load_settings()
        self.calculate_hours(settings)
        self.calculate_wage(settings)

    # ───────── Static query helpers ─────────
    @staticmethod
    def get_attendance_by_date(date):
        return Attendance.query.filter_by(date=date).all()

    @staticmethod
    def get_attendance_by_worker(worker_id, start_date=None, end_date=None):
        query = Attendance.query.filter_by(worker_id=worker_id)
        if start_date:
            query = query.filter(Attendance.date >= start_date)
        if end_date:
            query = query.filter(Attendance.date <= end_date)
        return query.order_by(Attendance.date.desc()).all()

    @staticmethod
    def get_attendance_by_team(team_id, start_date=None, end_date=None):
        query = Attendance.query.filter_by(team_id=team_id)
        if start_date:
            query = query.filter(Attendance.date >= start_date)
        if end_date:
            query = query.filter(Attendance.date <= end_date)
        return query.order_by(Attendance.date.desc()).all()

    @staticmethod
    def get_attendance_by_site(site_id, start_date=None, end_date=None):
        query = Attendance.query.filter_by(site_id=site_id)
        if start_date:
            query = query.filter(Attendance.date >= start_date)
        if end_date:
            query = query.filter(Attendance.date <= end_date)
        return query.order_by(Attendance.date.desc()).all()

    @staticmethod
    def get_attendance_by_date_range(start_date, end_date):
        return Attendance.query.filter(
            Attendance.date >= start_date,
            Attendance.date <= end_date
        ).order_by(Attendance.date.desc()).all()

    @staticmethod
    def get_attendance_summary(worker_id, start_date, end_date):
        records = Attendance.get_attendance_by_worker(worker_id, start_date, end_date)
        total_days = (end_date - start_date).days + 1
        total_present = sum(1 for r in records if r.present)
        total_hours = sum(max(0, r.total_hours or 0) for r in records)
        total_wages = sum(max(0, r.wage_earned or 0) for r in records)
        total_overtime = sum(max(0, r.overtime_hours or 0) for r in records)

        from .worker import Worker
        worker = Worker.query.get(worker_id)

        return {
            'worker_id': worker_id,
            'worker_name': worker.name if worker else 'Unknown',
            'total_days': total_days,
            'total_present': total_present,
            'total_absent': total_days - total_present,
            'total_hours': total_hours,
            'total_wages': total_wages,
            'total_overtime': total_overtime,
            'attendance_rate': (total_present / total_days * 100) if total_days > 0 else 0
        }

    @staticmethod
    def get_team_attendance_summary(team_id, start_date, end_date):
        from .team import WorkerTeam
        from .worker import Worker

        team = WorkerTeam.query.get(team_id)
        if not team:
            return None

        worker_ids = team.get_worker_ids()
        if not worker_ids:
            return {
                'team_id': team_id,
                'team_name': team.name,
                'total_members': 0,
                'total_days': 0,
                'total_present': 0,
                'total_hours': 0,
                'total_wages': 0,
                'attendance_rate': 0
            }

        records = Attendance.query.filter(
            Attendance.worker_id.in_(worker_ids),
            Attendance.date >= start_date,
            Attendance.date <= end_date
        ).all()

        total_days = (end_date - start_date).days + 1
        total_possible = len(worker_ids) * total_days
        total_present = sum(1 for r in records if r.present)
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

        return {
            'team_id': team_id,
            'team_name': team.name,
            'total_members': len(worker_ids),
            'total_days': total_days,
            'total_possible': total_possible,
            'total_present': total_present,
            'total_absent': total_possible - total_present,
            'total_hours': total_hours,
            'total_wages': total_wages,
            'attendance_rate': (total_present / total_possible * 100) if total_possible > 0 else 0,
            'worker_summary': worker_summary
        }

    @staticmethod
    def get_today_attendance():
        today = datetime.utcnow().date()
        return Attendance.query.filter_by(date=today).all()

    @staticmethod
    def get_currently_working():
        return Attendance.query.filter(
            Attendance.checked_in.isnot(None),
            Attendance.checked_out.is_(None)
        ).all()