# models/entry.py
from models import db
from datetime import datetime


class Entry(db.Model):
    __tablename__ = 'entries'
    id = db.Column(db.String(20), primary_key=True)
    date = db.Column(db.Date, nullable=False)
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)

    kamai = db.Column(db.Float, default=0.0)
    labour = db.Column(db.Float, default=0.0)
    overhead = db.Column(db.Float, default=0.0)
    one_time = db.Column(db.Float, default=0.0)
    material_cost = db.Column(db.Float, default=0.0)
    equipment_cost = db.Column(db.Float, default=0.0)
    transport_cost = db.Column(db.Float, default=0.0)
    other_expense = db.Column(db.Float, default=0.0)
    note = db.Column(db.Text)
    profit_loss = db.Column(db.Float, default=0.0)

    # NEW: source tracking
    source = db.Column(db.String(20), default='manual')      # 'manual' | 'auto' | 'mixed'
    manual_override = db.Column(db.Boolean, default=False)

    # NEW: audit of last auto-computation (so UI can show what auto would be)
    auto_kamai = db.Column(db.Float, default=0.0)
    auto_labour = db.Column(db.Float, default=0.0)
    auto_overhead = db.Column(db.Float, default=0.0)
    auto_one_time = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    site = db.relationship('Site', backref='entries')
    project = db.relationship('Project', backref='entries')

    def to_dict(self):
        profit = self.profit_loss if self.profit_loss is not None else (
            (self.kamai or 0) - (self.labour or 0) - (self.overhead or 0)
            - (self.one_time or 0) - (self.material_cost or 0)
            - (self.equipment_cost or 0) - (self.transport_cost or 0)
            - (self.other_expense or 0)
        )
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'siteId': self.site_id,
            'siteName': self.site.name if self.site else None,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'kamai': self.kamai or 0,
            'labour': self.labour or 0,
            'overhead': self.overhead or 0,
            'oneTime': self.one_time or 0,
            'materialCost': self.material_cost or 0,
            'equipmentCost': self.equipment_cost or 0,
            'transportCost': self.transport_cost or 0,
            'otherExpense': self.other_expense or 0,
            'profit': profit,
            'note': self.note,
            'source': self.source or 'manual',
            'manualOverride': bool(self.manual_override),
            'autoKamai': self.auto_kamai or 0,
            'autoLabour': self.auto_labour or 0,
            'autoOverhead': self.auto_overhead or 0,
            'autoOneTime': self.auto_one_time or 0,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }

    def calculate_profit(self):
        self.profit_loss = (
            (self.kamai or 0) - (self.labour or 0) - (self.overhead or 0)
            - (self.one_time or 0) - (self.material_cost or 0)
            - (self.equipment_cost or 0) - (self.transport_cost or 0)
            - (self.other_expense or 0)
        )
        return self.profit_loss

    @staticmethod
    def get_entries_by_site(site_id):
        return Entry.query.filter_by(site_id=site_id).order_by(Entry.date.desc()).all()

    @staticmethod
    def get_entries_by_project(project_id):
        return Entry.query.filter_by(project_id=project_id).order_by(Entry.date.desc()).all()

    @staticmethod
    def get_entries_by_month(month):
        return Entry.query.filter(Entry.date.like(f'{month}%')).all()

    @staticmethod
    def get_monthly_summary(month, site_id=None, project_id=None):
        query = Entry.query.filter(Entry.date.like(f'{month}%'))
        if site_id:
            query = query.filter_by(site_id=site_id)
        if project_id:
            query = query.filter_by(project_id=project_id)
        entries = query.all()

        total_kamai = sum(e.kamai or 0 for e in entries)
        total_labour = sum(e.labour or 0 for e in entries)
        total_overhead = sum(e.overhead or 0 for e in entries)
        total_one_time = sum(e.one_time or 0 for e in entries)
        total_material = sum(e.material_cost or 0 for e in entries)
        total_equipment = sum(e.equipment_cost or 0 for e in entries)
        total_transport = sum(e.transport_cost or 0 for e in entries)
        total_other = sum(e.other_expense or 0 for e in entries)
        total_profit = (
            total_kamai - total_labour - total_overhead - total_one_time
            - total_material - total_equipment - total_transport - total_other
        )

        return {
            'month': month,
            'totalEntries': len(entries),
            'totalKamai': total_kamai,
            'totalLabour': total_labour,
            'totalOverhead': total_overhead,
            'totalOneTime': total_one_time,
            'totalMaterial': total_material,
            'totalEquipment': total_equipment,
            'totalTransport': total_transport,
            'totalOther': total_other,
            'totalProfit': total_profit,
        }