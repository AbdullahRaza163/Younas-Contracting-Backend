from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
import json

db = SQLAlchemy()
migrate = Migrate()

# Association table for many-to-many relationships if needed
# For now, we'll keep it simple

class Site(db.Model):
    __tablename__ = 'sites'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    manager = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    entries = db.relationship('Entry', backref='site', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'manager': self.manager,
            'phone': self.phone,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Worker(db.Model):
    __tablename__ = 'workers'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50))
    daily_rate = db.Column(db.Float, default=0.0)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    attendance = db.relationship('Attendance', backref='worker', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'dailyRate': self.daily_rate,
            'phone': self.phone,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Entry(db.Model):
    __tablename__ = 'entries'
    
    id = db.Column(db.String(20), primary_key=True)
    date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id'), nullable=False)
    kamai = db.Column(db.Float, default=0.0)
    labour = db.Column(db.Float, default=0.0)
    overhead = db.Column(db.Float, default=0.0)
    one_time = db.Column(db.Float, default=0.0)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date,
            'siteId': self.site_id,
            'kamai': self.kamai,
            'labour': self.labour,
            'overhead': self.overhead,
            'oneTime': self.one_time,
            'note': self.note,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.String(20), primary_key=True)
    worker_id = db.Column(db.String(20), db.ForeignKey('workers.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    present = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'workerId': self.worker_id,
            'date': self.date,
            'present': self.present,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }

class Setting(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'key': self.key,
            'value': json.loads(self.value) if self.value else None
        }

# Helper function to generate ID
def generate_id():
    import random
    import string
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))