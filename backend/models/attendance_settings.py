# models/attendance_settings.py
from models import db
from datetime import datetime


class AttendanceSettings(db.Model):
    __tablename__ = 'attendance_settings'

    id = db.Column(db.Integer, primary_key=True, default=1)  # single row

    # ---------- Shift window ----------
    shift_start_time  = db.Column(db.String(5), default='07:00')   # HH:MM
    shift_end_time    = db.Column(db.String(5), default='17:00')   # HH:MM
    shift_hours       = db.Column(db.Float, default=8.0)           # hours/day

    # ---------- Break ----------
    break_start_time  = db.Column(db.String(5), default='12:00')   # HH:MM
    break_end_time    = db.Column(db.String(5), default='13:00')   # HH:MM
    break_hours       = db.Column(db.Float, default=1.0)           # hours
    break_enabled     = db.Column(db.Boolean, default=True, nullable=False)

    # ---------- Overtime ----------
    # ⭐ Set from the frontend Settings tab:
    #     1.0  → no premium (all OT hours paid at normal rate)
    #     1.5  → standard premium
    #     2.0  → double rate
    #     any other multiplier
    overtime_rate     = db.Column(db.Float, default=1.0)           # multiplier
    overtime_enabled  = db.Column(db.Boolean, default=True, nullable=False)

    # ---------- Thresholds (minutes) ----------
    early_in_threshold  = db.Column(db.Integer, default=15)
    late_in_threshold   = db.Column(db.Integer, default=15)
    early_out_threshold = db.Column(db.Integer, default=15)
    late_out_threshold  = db.Column(db.Integer, default=15)

    # ---------- Flags ----------
    count_early_in   = db.Column(db.Boolean, default=True)
    count_late_in    = db.Column(db.Boolean, default=True)
    count_early_out  = db.Column(db.Boolean, default=True)
    count_late_out   = db.Column(db.Boolean, default=True)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'shiftStartTime':   self.shift_start_time,
            'shiftEndTime':     self.shift_end_time,
            'shiftHours':       float(self.shift_hours or 8.0),

            'breakStartTime':   self.break_start_time,
            'breakEndTime':     self.break_end_time,
            'breakHours':       float(self.break_hours or 1.0),
            'breakEnabled':     bool(self.break_enabled),

            # ⭐ Fall back to 1.0 (not 1.5) if DB value is missing
            'overtimeRate':     float(self.overtime_rate if self.overtime_rate is not None else 1.0),
            'overtimeEnabled':  bool(self.overtime_enabled),

            'earlyInThreshold':  int(self.early_in_threshold or 15),
            'lateInThreshold':   int(self.late_in_threshold or 15),
            'earlyOutThreshold': int(self.early_out_threshold or 15),
            'lateOutThreshold':  int(self.late_out_threshold or 15),

            'countEarlyIn':     bool(self.count_early_in),
            'countLateIn':      bool(self.count_late_in),
            'countEarlyOut':    bool(self.count_early_out),
            'countLateOut':     bool(self.count_late_out),

            'updatedAt':        self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def get_settings():
        """Always return the single settings row, creating it if missing."""
        s = AttendanceSettings.query.get(1)
        if not s:
            s = AttendanceSettings(id=1)
            db.session.add(s)
            db.session.commit()
        return s