# models/attendance_shift.py
from models import db
from datetime import datetime, timezone


class AttendanceShift(db.Model):
    """
    One continuous work session on a specific site.

    A worker can have multiple shifts per day, each on a different site.
    Example: 08:00–11:00 on Site A, 11:15–17:00 on Site B.

    NOTE: Hours + wage are computed by `Attendance.recalc_from_shifts(...)`
    and stored here for fast reads. This model only stores + serializes.
    """
    __tablename__ = 'attendance_shifts'

    id = db.Column(db.String(20), primary_key=True)
    attendance_id = db.Column(
        db.String(20),
        db.ForeignKey('attendance.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='SET NULL'))
    order_index = db.Column(db.Integer, default=0)

    checked_in = db.Column(db.DateTime)
    checked_out = db.Column(db.DateTime)
    break_start = db.Column(db.DateTime)
    break_end = db.Column(db.DateTime)

    # Per-shift toggles (null = inherit global)
    break_enabled = db.Column(db.Boolean, nullable=True, default=None)
    overtime_enabled = db.Column(db.Boolean, nullable=True, default=None)

    # Computed (written by Attendance.recalc_from_shifts)
    normal_hours = db.Column(db.Float, default=0.0)
    overtime_hours = db.Column(db.Float, default=0.0)
    total_hours = db.Column(db.Float, default=0.0)
    wage_earned = db.Column(db.Float, default=0.0)

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    attendance = db.relationship('Attendance', backref=db.backref(
        'shifts', cascade='all, delete-orphan', order_by='AttendanceShift.order_index'
    ))
    site = db.relationship('Site')

    # ───────── Helpers ─────────
    @staticmethod
    def _to_naive_utc(dt):
        """Coerce an aware datetime → naive UTC. Naive stays as-is."""
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    def _safe(self, value, digits=2):
        """Round a numeric value safely (None → 0.0)."""
        try:
            return round(float(value or 0), digits)
        except (TypeError, ValueError):
            return 0.0

    def to_dict(self, site_name=None):
        """
        Serialize this shift.

        Notes:
          - `breakEnabled` / `overtimeEnabled` are None when unset,
            meaning the client should inherit the global setting.
          - All numeric fields are normalized to 2-decimal floats (3 for wage)
            so the UI never receives `null` for hours/wage.
        """
        return {
            'id': self.id,
            'attendanceId': self.attendance_id,
            'siteId': self.site_id,
            'siteName': site_name if site_name is not None
                        else (self.site.name if self.site else None),
            'orderIndex': self.order_index,
            'checkedIn': self.checked_in.isoformat() if self.checked_in else None,
            'checkedOut': self.checked_out.isoformat() if self.checked_out else None,
            'breakStart': self.break_start.isoformat() if self.break_start else None,
            'breakEnd': self.break_end.isoformat() if self.break_end else None,
            # ⭐ null = inherit global
            'breakEnabled': self.break_enabled,
            'overtimeEnabled': self.overtime_enabled,
            # ⭐ numeric fields always non-null
            'normalHours': self._safe(self.normal_hours),
            'overtimeHours': self._safe(self.overtime_hours),
            'totalHours': self._safe(self.total_hours),
            'wageEarned': self._safe(self.wage_earned, 3),
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }