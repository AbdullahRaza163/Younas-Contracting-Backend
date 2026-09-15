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
            'overtimeHours': self.overtime_hours,
            'normalHours': self.normal_hours,
            'totalHours': self.total_hours,
            'wageEarned': self.wage_earned,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }

    def calculate_hours(self):
        """
        Calculate normal and overtime hours.
        Robust against mixed naive/aware datetimes.
        Never returns negative values.
        """
        if not self.checked_in or not self.checked_out:
            return

        checked_in = self.checked_in
        checked_out = self.checked_out

        # ⭐ Normalize both to naive UTC
        if checked_in.tzinfo is not None:
            checked_in = checked_in.astimezone(timezone.utc).replace(tzinfo=None)
        if checked_out.tzinfo is not None:
            checked_out = checked_out.astimezone(timezone.utc).replace(tzinfo=None)

        total_seconds = (checked_out - checked_in).total_seconds()

        # ⭐ Clamp negative (mixed timezones / bad data)
        if total_seconds < 0:
            self.total_hours = 0.0
            self.normal_hours = 0.0
            self.overtime_hours = 0.0
            return

        # Subtract break time if exists
        if self.break_start and self.break_end:
            bs = self.break_start
            be = self.break_end
            if bs.tzinfo is not None:
                bs = bs.astimezone(timezone.utc).replace(tzinfo=None)
            if be.tzinfo is not None:
                be = be.astimezone(timezone.utc).replace(tzinfo=None)
            total_seconds -= (be - bs).total_seconds()

        total_hours = max(0.0, total_seconds / 3600)
        self.total_hours = round(total_hours, 2)

        if total_hours > 8:
            self.normal_hours = 8.0
            self.overtime_hours = round(total_hours - 8, 2)
        else:
            self.normal_hours = round(total_hours, 2)
            self.overtime_hours = 0.0

    def calculate_wage(self):
        """Calculate wage earned based on worker's hourly rate. Never negative."""
        if self.worker:
            normal = max(0.0, self.normal_hours or 0.0)
            overtime = max(0.0, self.overtime_hours or 0.0)
            base_wage = normal * self.worker.hourly_rate
            overtime_wage = overtime * self.worker.hourly_rate * 1.5
            self.wage_earned = round(max(0.0, base_wage + overtime_wage), 2)
        return self.wage_earned

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
        # ⭐ Guard: never earlier than checked_in
        if self.checked_in and t < self.checked_in:
            t = self.checked_in
        self.checked_out = t
        self.calculate_hours()
        self.calculate_wage()

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
        # ⭐ Clamp negatives
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
        # ⭐ Clamp negatives
        total_hours = sum(max(0, r.total_hours or 0) for r in records)
        total_wages = sum(max(0, r.wage_earned or 0) for r in records)

        # ⭐ Group by worker in one pass — O(n) instead of O(n²)
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