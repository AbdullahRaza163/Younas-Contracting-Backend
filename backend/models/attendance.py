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
    # ⭐ Also exposes the full shifts array for multi-site days
    def to_dict(self, site_name=None, worker_name=None):
        # ── Build the shifts array ──
        shift_list = []
        try:
            from models.attendance_shift import AttendanceShift
            from models.site import Site

            shifts = AttendanceShift.query.filter_by(attendance_id=self.id) \
                .order_by(AttendanceShift.order_index).all()

            # Batch-load site names to avoid N+1
            site_ids = {s.site_id for s in shifts if s.site_id}
            sites_map = {}
            if site_ids:
                for s in Site.query.filter(Site.id.in_(site_ids)).all():
                    sites_map[s.id] = s.name

            shift_list = [
                s.to_dict(site_name=sites_map.get(s.site_id))
                for s in shifts
            ]
        except Exception as e:
            print(f"[Attendance.to_dict] failed to load shifts: {e}")

        has_shifts = len(shift_list) > 0

        # ── Aggregate hours + wages from shifts when they exist ──
        if has_shifts:
            agg_total = round(sum(s.get('totalHours') or 0 for s in shift_list), 2)
            agg_normal = round(sum(s.get('normalHours') or 0 for s in shift_list), 2)
            agg_ot = round(sum(s.get('overtimeHours') or 0 for s in shift_list), 2)
            agg_wage = round(sum(s.get('wageEarned') or 0 for s in shift_list), 3)
        else:
            agg_total = self.total_hours
            agg_normal = self.normal_hours
            agg_ot = self.overtime_hours
            agg_wage = self.wage_earned

        # ── Primary site = the biggest shift ──
        primary_site_id = self.site_id
        primary_site_name = site_name
        if has_shifts:
            biggest = max(shift_list, key=lambda s: s.get('totalHours') or 0)
            primary_site_id = biggest.get('siteId') or primary_site_id
            primary_site_name = biggest.get('siteName') or primary_site_name

        return {
            'id': self.id,
            'workerId': self.worker_id,
            'workerName': worker_name if worker_name is not None
                          else (self.worker.name if self.worker else None),
            'teamId': self.team_id,
            'siteId': primary_site_id,
            'siteName': primary_site_name,
            'date': self.date.isoformat() if self.date else None,
            'checkedIn': self.checked_in.isoformat() if self.checked_in else None,
            'checkedOut': self.checked_out.isoformat() if self.checked_out else None,
            'breakStart': self.break_start.isoformat() if self.break_start else None,
            'breakEnd': self.break_end.isoformat() if self.break_end else None,
            'present': self.present,
            # ⭐ null means inherit global setting
            'breakEnabled': self.break_enabled,
            'overtimeEnabled': self.overtime_enabled,
            'overtimeHours': agg_ot,
            'normalHours': agg_normal,
            'totalHours': agg_total,
            'wageEarned': agg_wage,
            'notes': self.notes,
            # ⭐ Multi-site
            'shifts': shift_list,
            'hasShifts': has_shifts,
            'siteCount': len(shift_list),
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
            'overtime_rate': 1.0,          # ⭐ default = 1.0 (no premium)
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

    @staticmethod
    def _resolve_hourly_rate(worker, shift_hours):
        """
        Effective hourly rate.

        ⭐ Single-field setup: your Workers module has ONE rate field
        that you intend as an HOURLY rate. The backend stores it in
        `daily_rate` (legacy column name). We therefore treat `daily_rate`
        AS-IS — no division by shift_hours.

        Priority:
          1. worker.hourly_rate (if > 0)  → use directly
          2. worker.daily_rate  (if > 0)  → use directly (it IS the hourly rate)
          3. 0
        """
        if not worker:
            return 0.0
        h = float(getattr(worker, 'hourly_rate', 0) or 0)
        if h > 0:
            return h
        d = float(getattr(worker, 'daily_rate', 0) or 0)
        if d > 0:
            return d
        return 0.0

    @staticmethod
    def _to_naive_utc(dt):
        """Coerce an aware datetime → naive UTC. Naive stays as-is."""
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    # ───────── Calculations ─────────
    def calculate_hours(self, settings=None):
        """
        Calculate normal and overtime hours for a LEGACY (no-shifts) record.

        Rules:
          - Break subtracted if break_enabled:
              * Prefer explicit break_start/break_end timestamps.
              * ⭐ FALL BACK to settings['break_hours'] when timestamps missing.
          - OT = hours beyond shift_hours (only when overtime_enabled).
          - Never negative.
          - Uses rounded total for the split so normal + OT == total exactly.
        """
        if not self.checked_in or not self.checked_out:
            return

        if settings is None:
            settings = self._load_settings()

        checked_in = self._to_naive_utc(self.checked_in)
        checked_out = self._to_naive_utc(self.checked_out)

        total_seconds = (checked_out - checked_in).total_seconds()

        # Clamp negative (mixed timezones / bad data)
        if total_seconds < 0:
            self.total_hours = 0.0
            self.normal_hours = 0.0
            self.overtime_hours = 0.0
            return

        # ⭐ Break subtraction — ONLY if break is enabled
        break_enabled = self._resolve_break_enabled(settings)
        if break_enabled:
            if self.break_start and self.break_end:
                bs = self._to_naive_utc(self.break_start)
                be = self._to_naive_utc(self.break_end)
                break_seconds = (be - bs).total_seconds()
                if break_seconds > 0:
                    total_seconds -= break_seconds
            else:
                # ⭐ FALLBACK: use configured break_hours
                cfg_break_hours = float(settings.get('break_hours', 0) or 0)
                if cfg_break_hours > 0:
                    total_seconds -= cfg_break_hours * 3600.0

        total_hours = max(0.0, total_seconds / 3600)
        self.total_hours = round(total_hours, 2)

        # ⭐ OT split — respects OT toggle & configured shift hours
        overtime_enabled = self._resolve_overtime_enabled(settings)
        shift_hours = float(settings.get('shift_hours', 8.0)) or 8.0

        # ⭐ FIX: use the rounded total for the split so normal + OT == total
        rounded_total = self.total_hours
        if overtime_enabled and rounded_total > shift_hours:
            self.normal_hours = round(shift_hours, 2)
            self.overtime_hours = round(rounded_total - shift_hours, 2)
        else:
            # OT disabled → everything is normal hours
            self.normal_hours = round(rounded_total, 2)
            self.overtime_hours = 0.0

    def calculate_wage(self, settings=None):
        """
        Calculate wage for a LEGACY (no-shifts) record.

        Rules:
          - hourly_rate = worker.hourly_rate (as-is, BD/hour)
                          else worker.daily_rate (as-is — single-field setup)
          - OT paid at overtime_rate ONLY when OT is enabled.
          - Never negative.
        """
        if settings is None:
            settings = self._load_settings()

        if not self.worker:
            self.wage_earned = 0.0
            return self.wage_earned

        shift_hours = float(settings.get('shift_hours', 8.0)) or 8.0
        hourly_rate = self._resolve_hourly_rate(self.worker, shift_hours)

        normal = max(0.0, self.normal_hours or 0.0)
        overtime = max(0.0, self.overtime_hours or 0.0)

        base_wage = normal * hourly_rate

        overtime_enabled = self._resolve_overtime_enabled(settings)
        ot_rate = float(settings.get('overtime_rate', 1.0)) or 1.0
        if overtime_enabled:
            overtime_wage = overtime * hourly_rate * ot_rate
        else:
            overtime_wage = 0.0

        self.wage_earned = round(max(0.0, base_wage + overtime_wage), 3)
        return self.wage_earned

    # ────────────────────────────────────────────
    # ⭐ Recompute from shifts (multi-site)
    # ────────────────────────────────────────────
    def recalc_from_shifts(self, settings=None):
        """
        Aggregate hours + wages across all `attendance_shifts`.

        Rules:
          - Each shift's break/OT toggles override the global settings.
          - ⭐ FALL BACK to settings['break_hours'] when a shift has
            break enabled but no explicit break_start/break_end.
          - OT split per shift: hours beyond shift_hours (only if OT on).
          - Wage = sum(shift normal × rate + shift OT × rate × ot_rate).
          - Mirrors overall clock-in/out and primary site back to parent.
        """
        if settings is None:
            settings = self._load_settings()

        from models.attendance_shift import AttendanceShift
        shifts = AttendanceShift.query.filter_by(attendance_id=self.id) \
            .order_by(AttendanceShift.order_index).all()

        if not shifts:
            return  # keep legacy single-session values

        shift_hours = float(settings.get('shift_hours', 8.0)) or 8.0
        ot_rate = float(settings.get('overtime_rate', 1.0)) or 1.0
        global_break_enabled = bool(settings.get('break_enabled', True))
        global_break_hours = float(settings.get('break_hours', 0) or 0)
        global_ot_enabled = bool(settings.get('overtime_enabled', True))

        hourly_rate = self._resolve_hourly_rate(self.worker, shift_hours)

        # ── Step 1: compute each shift's raw totals ──
        for sh in shifts:
            sh_total_hours = 0.0
            sh_normal = 0.0
            sh_ot = 0.0
            ot_enabled_for_wage = sh.overtime_enabled if sh.overtime_enabled is not None \
                else global_ot_enabled

            if sh.checked_in and sh.checked_out:
                ci = self._to_naive_utc(sh.checked_in)
                co = self._to_naive_utc(sh.checked_out)

                raw = (co - ci).total_seconds()
                if raw < 0:
                    raw = 0

                # ⭐ Per-shift break toggle → global fallback
                break_enabled = sh.break_enabled if sh.break_enabled is not None \
                    else global_break_enabled

                if break_enabled:
                    if sh.break_start and sh.break_end:
                        bs = self._to_naive_utc(sh.break_start)
                        be = self._to_naive_utc(sh.break_end)
                        bs_sec = (be - bs).total_seconds()
                        if bs_sec > 0:
                            raw -= bs_sec
                    else:
                        # ⭐ FALLBACK: use configured break_hours
                        if global_break_hours > 0:
                            raw -= global_break_hours * 3600.0

                sh_total_hours = max(0.0, raw / 3600)

                # ⭐ Per-shift OT toggle → global fallback
                ot_enabled = sh.overtime_enabled if sh.overtime_enabled is not None \
                    else global_ot_enabled

                if ot_enabled and sh_total_hours > shift_hours:
                    sh_normal = shift_hours
                    sh_ot = sh_total_hours - shift_hours
                else:
                    sh_normal = sh_total_hours
                    sh_ot = 0.0

            # Wage for this shift — OT only multiplies when OT is enabled
            base_wage = sh_normal * hourly_rate
            if ot_enabled_for_wage:
                ot_wage = sh_ot * hourly_rate * ot_rate
            else:
                ot_wage = 0.0

            sh.normal_hours = round(sh_normal, 2)
            sh.overtime_hours = round(sh_ot, 2)
            sh.total_hours = round(sh_total_hours, 2)
            sh.wage_earned = round(max(0.0, base_wage + ot_wage), 3)

        # ── Step 2: aggregate into the parent record ──
        self.total_hours = round(sum(s.total_hours or 0 for s in shifts), 2)
        self.normal_hours = round(sum(s.normal_hours or 0 for s in shifts), 2)
        self.overtime_hours = round(sum(s.overtime_hours or 0 for s in shifts), 2)
        self.wage_earned = round(sum(s.wage_earned or 0 for s in shifts), 3)

        # Mirror overall clock-in/out for legacy consumers
        if shifts:
            first_in = next((s.checked_in for s in shifts if s.checked_in), None)
            last_out = None
            for s in shifts:
                if s.checked_out and (last_out is None or s.checked_out > last_out):
                    last_out = s.checked_out
            if first_in:
                self.checked_in = first_in
            if last_out:
                self.checked_out = last_out
            # Primary site = biggest shift
            biggest = max(shifts, key=lambda s: s.total_hours or 0)
            if biggest.site_id:
                self.site_id = biggest.site_id

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

        # ⭐ If this record has shifts, recalc from shifts; else legacy calc
        from models.attendance_shift import AttendanceShift
        has_shifts = AttendanceShift.query.filter_by(attendance_id=self.id).first() is not None
        if has_shifts:
            self.recalc_from_shifts(settings)
        else:
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