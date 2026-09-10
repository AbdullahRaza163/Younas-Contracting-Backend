# models/equipment.py
from models import db
from datetime import datetime
import random
import string
from models.site import Site
from models.worker import Worker

class EquipmentCategory(db.Model):
    __tablename__ = 'equipment_categories'

    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    equipment = db.relationship('Equipment', backref='category_ref', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'equipmentCount': self.equipment.count(),
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class Equipment(db.Model):
    __tablename__ = 'equipment'

    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    category_id = db.Column(db.String(20), db.ForeignKey('equipment_categories.id', ondelete='SET NULL'))

    manufacturer = db.Column(db.String(100))
    model = db.Column(db.String(100))
    serial_number = db.Column(db.String(100))
    year_manufactured = db.Column(db.Integer)
    purchase_date = db.Column(db.Date)
    purchase_price = db.Column(db.Float, default=0.0)
    current_value = db.Column(db.Float, default=0.0)
    depreciation_method = db.Column(db.String(50), default='straight_line')
    depreciation_rate = db.Column(db.Float, default=10.0)
    useful_life_years = db.Column(db.Integer, default=5)
    salvage_value = db.Column(db.Float, default=0.0)

    # Status & Location
    status = db.Column(db.String(20), default='available')
    condition = db.Column(db.String(20), default='good')
    location = db.Column(db.String(200))
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='SET NULL'))
    assigned_to_worker_id = db.Column(db.String(20), db.ForeignKey('workers.id', ondelete='SET NULL'))

    # Operational
    last_maintenance_date = db.Column(db.Date)
    next_maintenance_date = db.Column(db.Date)
    maintenance_interval_days = db.Column(db.Integer, default=30)
    total_hours_used = db.Column(db.Float, default=0.0)
    total_cost_accumulated = db.Column(db.Float, default=0.0)

    # Documents
    warranty_expiry = db.Column(db.Date)
    insurance_policy = db.Column(db.String(100))
    insurance_expiry = db.Column(db.Date)

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category = db.relationship('EquipmentCategory', backref='equipment_items')
    site = db.relationship('Site', backref='equipment')
    assigned_to_worker = db.relationship('Worker', backref='assigned_equipment')
    maintenance_records = db.relationship('EquipmentMaintenance', backref='equipment', lazy='dynamic', cascade='all, delete-orphan')
    assignments = db.relationship('EquipmentAssignment', backref='equipment', lazy='dynamic', cascade='all, delete-orphan')
    usage_records = db.relationship('EquipmentUsage', backref='equipment', lazy='dynamic', cascade='all, delete-orphan')
    depreciation_records = db.relationship('EquipmentDepreciation', backref='equipment', lazy='dynamic', cascade='all, delete-orphan')

    # ------------------------------------------------------------------
    # Helper: current active assignment (not yet returned)
    # ------------------------------------------------------------------
    def get_active_assignment(self):
        """Return the current open assignment, or None if unassigned."""
        try:
            return EquipmentAssignment.query.filter_by(
                equipment_id=self.id,
                actual_return_date=None
            ).order_by(EquipmentAssignment.assigned_date.desc()).first()
        except Exception:
            return None

    def to_dict(self):
        # Embed the active assignment so the frontend can render site
        # info on the equipment card without a second API call.
        active = self.get_active_assignment()

        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'categoryId': self.category_id,
            'categoryName': self.category.name if self.category else None,
            'categoryIcon': self.category.icon if self.category else None,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'serialNumber': self.serial_number,
            'yearManufactured': self.year_manufactured,
            'purchaseDate': self.purchase_date.isoformat() if self.purchase_date else None,
            'purchasePrice': self.purchase_price,
            'currentValue': self.current_value,
            'depreciationMethod': self.depreciation_method,
            'depreciationRate': self.depreciation_rate,
            'usefulLifeYears': self.useful_life_years,
            'salvageValue': self.salvage_value,
            'status': self.status,
            'condition': self.condition,
            'location': self.location,
            'siteId': self.site_id,
            'siteName': self.site.name if self.site else None,
            'assignedToWorkerId': self.assigned_to_worker_id,
            'assignedToWorkerName': self.assigned_to_worker.name if self.assigned_to_worker else None,
            'lastMaintenanceDate': self.last_maintenance_date.isoformat() if self.last_maintenance_date else None,
            'nextMaintenanceDate': self.next_maintenance_date.isoformat() if self.next_maintenance_date else None,
            'maintenanceIntervalDays': self.maintenance_interval_days,
            'totalHoursUsed': self.total_hours_used,
            'totalCostAccumulated': self.total_cost_accumulated,
            'warrantyExpiry': self.warranty_expiry.isoformat() if self.warranty_expiry else None,
            'insurancePolicy': self.insurance_policy,
            'insuranceExpiry': self.insurance_expiry.isoformat() if self.insurance_expiry else None,
            'notes': self.notes,
            # ---- Active assignment (flattened for the frontend) ----
            'activeAssignmentId': active.id if active else None,
            'activeAssignedToType': active.assigned_to_type if active else None,
            'activeAssignedToId': active.assigned_to_id if active else None,
            'activeAssignedDate': active.assigned_date.isoformat() if active and active.assigned_date else None,
            'activeExpectedReturnDate': active.expected_return_date.isoformat() if active and active.expected_return_date else None,
            'activeAssignmentNotes': active.notes if active else None,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }

    def calculate_depreciation(self):
        """Calculate depreciation based on method"""
        if self.depreciation_method == 'straight_line':
            yearly_depreciation = (self.purchase_price - self.salvage_value) / (self.useful_life_years or 1)
            return yearly_depreciation / 12  # Monthly depreciation
        elif self.depreciation_method == 'declining_balance':
            return self.current_value * (self.depreciation_rate / 100) / 12
        return 0

    def update_status_based_on_condition(self):
        """Update status based on condition"""
        if self.condition in ['excellent', 'good'] and self.status != 'assigned':
            self.status = 'available'
        elif self.condition in ['fair']:
            self.status = 'maintenance'
        elif self.condition in ['poor', 'critical']:
            self.status = 'repair'
        return self.status

    @staticmethod
    def generate_code():
        """Generate unique equipment code"""
        year = datetime.now().year
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f'EQP-{year}-{random_str}'

    @staticmethod
    def get_by_status(status):
        return Equipment.query.filter_by(status=status).all()

    @staticmethod
    def get_available():
        return Equipment.query.filter_by(status='available').all()

    @staticmethod
    def get_by_site(site_id):
        return Equipment.query.filter_by(site_id=site_id).all()


class EquipmentMaintenance(db.Model):
    __tablename__ = 'equipment_maintenance'

    id = db.Column(db.String(20), primary_key=True)
    equipment_id = db.Column(db.String(20), db.ForeignKey('equipment.id', ondelete='CASCADE'), nullable=False)
    maintenance_date = db.Column(db.Date, nullable=False)
    maintenance_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    cost = db.Column(db.Float, default=0.0)
    performed_by = db.Column(db.String(100))
    vendor = db.Column(db.String(100))
    hours_spent = db.Column(db.Float, default=0.0)
    next_maintenance_date = db.Column(db.Date)
    parts_replaced = db.Column(db.Text)
    status = db.Column(db.String(20), default='completed')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'equipmentId': self.equipment_id,
            'equipmentName': self.equipment.name if self.equipment else None,
            'maintenanceDate': self.maintenance_date.isoformat() if self.maintenance_date else None,
            'maintenanceType': self.maintenance_type,
            'description': self.description,
            'cost': self.cost,
            'performedBy': self.performed_by,
            'vendor': self.vendor,
            'hoursSpent': self.hours_spent,
            'nextMaintenanceDate': self.next_maintenance_date.isoformat() if self.next_maintenance_date else None,
            'partsReplaced': self.parts_replaced,
            'status': self.status,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }


class EquipmentAssignment(db.Model):
    __tablename__ = 'equipment_assignments'

    id = db.Column(db.String(20), primary_key=True)
    equipment_id = db.Column(db.String(20), db.ForeignKey('equipment.id', ondelete='CASCADE'), nullable=False)
    assigned_to_type = db.Column(db.String(20), nullable=False)   # 'site' | 'worker'
    assigned_to_id = db.Column(db.String(20), nullable=False)
    assigned_date = db.Column(db.Date, nullable=False)
    expected_return_date = db.Column(db.Date)
    actual_return_date = db.Column(db.Date)
    condition_on_return = db.Column(db.String(20))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Optional: resolve site/worker names for the frontend timeline
    def _resolve_assigned_name(self):
        try:
            if self.assigned_to_type == 'site':
                site = db.session.get(Site, self.assigned_to_id)
                return site.name if site else None
            elif self.assigned_to_type == 'worker':
                worker = db.session.get(Worker, self.assigned_to_id)
                return worker.name if worker else None
        except Exception:
            return None
        return None

    def to_dict(self):
        return {
            'id': self.id,
            'equipmentId': self.equipment_id,
            'equipmentName': self.equipment.name if self.equipment else None,
            'assignedToType': self.assigned_to_type,
            'assignedToId': self.assigned_to_id,
            'assignedToName': self._resolve_assigned_name(),
            'assignedDate': self.assigned_date.isoformat() if self.assigned_date else None,
            'expectedReturnDate': self.expected_return_date.isoformat() if self.expected_return_date else None,
            'actualReturnDate': self.actual_return_date.isoformat() if self.actual_return_date else None,
            'conditionOnReturn': self.condition_on_return,
            'notes': self.notes,
            'isActive': self.actual_return_date is None,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }


class EquipmentUsage(db.Model):
    __tablename__ = 'equipment_usage'

    id = db.Column(db.String(20), primary_key=True)
    equipment_id = db.Column(db.String(20), db.ForeignKey('equipment.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    hours_used = db.Column(db.Float, default=0.0)
    fuel_used = db.Column(db.Float, default=0.0)
    fuel_cost = db.Column(db.Float, default=0.0)
    operator_name = db.Column(db.String(100))
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='SET NULL'))
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='SET NULL'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    site = db.relationship('Site', backref='equipment_usage')
    project = db.relationship('Project', backref='equipment_usage')

    def to_dict(self):
        return {
            'id': self.id,
            'equipmentId': self.equipment_id,
            'equipmentName': self.equipment.name if self.equipment else None,
            'date': self.date.isoformat() if self.date else None,
            'hoursUsed': self.hours_used,
            'fuelUsed': self.fuel_used,
            'fuelCost': self.fuel_cost,
            'operatorName': self.operator_name,
            'siteId': self.site_id,
            'siteName': self.site.name if self.site else None,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }


class EquipmentDepreciation(db.Model):
    __tablename__ = 'equipment_depreciation'

    id = db.Column(db.String(20), primary_key=True)
    equipment_id = db.Column(db.String(20), db.ForeignKey('equipment.id', ondelete='CASCADE'), nullable=False)
    period_date = db.Column(db.Date, nullable=False)
    period_type = db.Column(db.String(20), default='monthly')
    beginning_value = db.Column(db.Float, default=0.0)
    depreciation_amount = db.Column(db.Float, default=0.0)
    ending_value = db.Column(db.Float, default=0.0)
    accumulated_depreciation = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'equipmentId': self.equipment_id,
            'equipmentName': self.equipment.name if self.equipment else None,
            'periodDate': self.period_date.isoformat() if self.period_date else None,
            'periodType': self.period_type,
            'beginningValue': self.beginning_value,
            'depreciationAmount': self.depreciation_amount,
            'endingValue': self.ending_value,
            'accumulatedDepreciation': self.accumulated_depreciation,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }