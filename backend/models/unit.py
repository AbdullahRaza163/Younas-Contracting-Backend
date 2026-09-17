# models/unit.py
from datetime import datetime, timezone
from models import db


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Unit(db.Model):
    """Isolated table for units of measurement."""
    __tablename__ = 'units'

    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True, index=True)
    symbol = db.Column(db.String(20), default='')
    category = db.Column(db.String(50), default='General', index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    sort_order = db.Column(db.Integer, default=0, index=True)
    created_at = db.Column(db.DateTime, default=_utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'symbol': self.symbol or '',
            'category': self.category or 'General',
            'isActive': bool(self.is_active),
            'sortOrder': int(self.sort_order or 0),
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }