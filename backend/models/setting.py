from models import db
from datetime import datetime
import json

class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    category = db.Column(db.String(50), default='general')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        try:
            return {
                'key': self.key,
                'value': json.loads(self.value) if self.value else None,
                'category': self.category
            }
        except:
            return {
                'key': self.key,
                'value': self.value,
                'category': self.category
            }
    
    def get_value_parsed(self):
        """Get parsed value (try JSON first, fallback to raw)"""
        try:
            return json.loads(self.value) if self.value else None
        except:
            return self.value
    
    def set_value(self, value):
        """Set value (will try to store as JSON if dict/list)"""
        if isinstance(value, (dict, list)):
            self.value = json.dumps(value)
        else:
            self.value = str(value)
    
    @staticmethod
    def get_setting(key, default=None):
        """Get a setting by key"""
        setting = Setting.query.filter_by(key=key).first()
        if setting:
            return setting.get_value_parsed()
        return default
    
    @staticmethod
    def set_setting(key, value, category='general'):
        """Set a setting value"""
        setting = Setting.query.filter_by(key=key).first()
        if setting:
            setting.set_value(value)
            setting.category = category
        else:
            setting = Setting(key=key, category=category)
            setting.set_value(value)
            db.session.add(setting)
        db.session.commit()
        return setting