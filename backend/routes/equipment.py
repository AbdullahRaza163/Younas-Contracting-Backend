# routes/equipment.py
from flask import request, jsonify
from models import (
    db, Equipment, EquipmentCategory, EquipmentMaintenance,
    EquipmentAssignment, EquipmentUsage, EquipmentDepreciation,
    Site, Worker, Project
)
from utils.helpers import generate_id
from routes import equipment_bp
from datetime import datetime, timedelta


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


# ============================================
# EQUIPMENT CRUD
# ============================================

@equipment_bp.route('', methods=['GET'])
def get_equipment():
    """Get all equipment with filters"""
    try:
        status = request.args.get('status')
        category_id = request.args.get('categoryId')
        site_id = request.args.get('siteId')
        search = request.args.get('search')

        query = Equipment.query
        if status:
            query = query.filter_by(status=status)
        if category_id:
            query = query.filter_by(category_id=category_id)
        if site_id:
            query = query.filter_by(site_id=site_id)
        if search:
            query = query.filter(
                db.or_(
                    Equipment.name.ilike(f'%{search}%'),
                    Equipment.code.ilike(f'%{search}%'),
                    Equipment.model.ilike(f'%{search}%')
                )
            )

        equipment = query.order_by(Equipment.name).all()
        return jsonify([e.to_dict() for e in equipment])
    except Exception as e:
        print(f"Error in get_equipment: {str(e)}")
        return jsonify({'error': str(e)}), 500


@equipment_bp.route('/<equipment_id>', methods=['GET'])
def get_equipment_item(equipment_id):
    """Get a specific equipment item with related counts and current assignment"""
    try:
        item = Equipment.query.get_or_404(equipment_id)
        data = item.to_dict()
        data['maintenanceCount'] = item.maintenance_records.count()
        data['assignmentCount'] = item.assignments.count()
        data['usageCount'] = item.usage_records.count()
        data['totalMaintenanceCost'] = sum(float(m.cost or 0) for m in item.maintenance_records.all())

        active = item.get_active_assignment()
        data['activeAssignment'] = active.to_dict() if active else None

        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@equipment_bp.route('', methods=['POST'])
def create_equipment():
    """Create new equipment"""
    try:
        data = request.json

        equipment = Equipment(
            id=generate_id(),
            name=data.get('name'),
            code=Equipment.generate_code(),
            category_id=data.get('categoryId'),
            manufacturer=data.get('manufacturer'),
            model=data.get('model'),
            serial_number=data.get('serialNumber'),
            year_manufactured=int(data['yearManufactured']) if data.get('yearManufactured') else None,
            purchase_date=_parse_date(data.get('purchaseDate')),
            purchase_price=float(data.get('purchasePrice') or 0),
            current_value=float(data.get('purchasePrice') or 0),
            depreciation_method=data.get('depreciationMethod', 'straight_line'),
            depreciation_rate=float(data.get('depreciationRate') or 10),
            useful_life_years=int(data.get('usefulLifeYears') or 5),
            salvage_value=float(data.get('salvageValue') or 0),
            status=data.get('status', 'available'),
            condition=data.get('condition', 'good'),
            location=data.get('location'),
            site_id=data.get('siteId') or None,
            assigned_to_worker_id=data.get('assignedToWorkerId') or None,
            maintenance_interval_days=int(data.get('maintenanceIntervalDays') or 30),
            warranty_expiry=_parse_date(data.get('warrantyExpiry')),
            insurance_policy=data.get('insurancePolicy'),
            insurance_expiry=_parse_date(data.get('insuranceExpiry')),
            notes=data.get('notes')
        )

        db.session.add(equipment)
        db.session.commit()

        # If a site was chosen at create time, also create an assignment record
        if equipment.site_id and equipment.status == 'assigned':
            db.session.add(EquipmentAssignment(
                id=generate_id(),
                equipment_id=equipment.id,
                assigned_to_type='site',
                assigned_to_id=equipment.site_id,
                assigned_date=datetime.now().date(),
                notes='Assigned during creation'
            ))
            db.session.commit()

        return jsonify(equipment.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_equipment: {str(e)}")
        return jsonify({'error': str(e)}), 400


@equipment_bp.route('/<equipment_id>', methods=['PUT'])
def update_equipment(equipment_id):
    """Update equipment"""
    try:
        equipment = Equipment.query.get_or_404(equipment_id)
        data = request.json

        if 'name' in data:
            equipment.name = data['name']
        if 'categoryId' in data:
            equipment.category_id = data['categoryId']
        if 'manufacturer' in data:
            equipment.manufacturer = data['manufacturer']
        if 'model' in data:
            equipment.model = data['model']
        if 'serialNumber' in data:
            equipment.serial_number = data['serialNumber']
        if 'yearManufactured' in data:
            equipment.year_manufactured = int(data['yearManufactured']) if data['yearManufactured'] else None
        if 'purchaseDate' in data:
            equipment.purchase_date = _parse_date(data['purchaseDate'])
        if 'purchasePrice' in data:
            equipment.purchase_price = float(data['purchasePrice'] or 0)
        if 'status' in data:
            equipment.status = data['status']
        if 'condition' in data:
            equipment.condition = data['condition']
        if 'location' in data:
            equipment.location = data['location']
        if 'siteId' in data:
            equipment.site_id = data['siteId'] or None
        if 'assignedToWorkerId' in data:
            equipment.assigned_to_worker_id = data['assignedToWorkerId'] or None

        # New fields that were previously ignored
        if 'maintenanceIntervalDays' in data:
            equipment.maintenance_interval_days = int(data['maintenanceIntervalDays'] or 30)
        if 'warrantyExpiry' in data:
            equipment.warranty_expiry = _parse_date(data['warrantyExpiry'])
        if 'insurancePolicy' in data:
            equipment.insurance_policy = data['insurancePolicy']
        if 'insuranceExpiry' in data:
            equipment.insurance_expiry = _parse_date(data['insuranceExpiry'])
        if 'notes' in data:
            equipment.notes = data['notes']

        db.session.commit()
        return jsonify(equipment.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_equipment: {str(e)}")
        return jsonify({'error': str(e)}), 400


@equipment_bp.route('/<equipment_id>', methods=['DELETE'])
def delete_equipment(equipment_id):
    """Delete equipment"""
    try:
        equipment = Equipment.query.get_or_404(equipment_id)
        db.session.delete(equipment)
        db.session.commit()
        return jsonify({'message': 'Equipment deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ============================================
# MAINTENANCE ROUTES
# ============================================

@equipment_bp.route('/<equipment_id>/maintenance', methods=['POST'])
def add_maintenance(equipment_id):
    """Add maintenance record"""
    try:
        data = request.json
        maintenance = EquipmentMaintenance(
            id=generate_id(),
            equipment_id=equipment_id,
            maintenance_date=_parse_date(data.get('maintenanceDate')) or datetime.now().date(),
            maintenance_type=data.get('maintenanceType', 'routine'),
            description=data.get('description'),
            cost=float(data.get('cost') or 0),
            performed_by=data.get('performedBy'),
            vendor=data.get('vendor'),
            hours_spent=float(data.get('hoursSpent') or 0),
            next_maintenance_date=_parse_date(data.get('nextMaintenanceDate')),
            parts_replaced=data.get('partsReplaced'),
            status=data.get('status', 'completed'),
            notes=data.get('notes')
        )

        equipment = Equipment.query.get(equipment_id)
        if equipment:
            equipment.last_maintenance_date = maintenance.maintenance_date
            if maintenance.next_maintenance_date:
                equipment.next_maintenance_date = maintenance.next_maintenance_date
            equipment.total_cost_accumulated = (equipment.total_cost_accumulated or 0) + maintenance.cost

        db.session.add(maintenance)
        db.session.commit()

        return jsonify(maintenance.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in add_maintenance: {str(e)}")
        return jsonify({'error': str(e)}), 400


@equipment_bp.route('/maintenance', methods=['GET'])
def get_maintenance_records():
    """Get all maintenance records (optionally filtered)"""
    try:
        equipment_id = request.args.get('equipmentId')
        maintenance_type = request.args.get('type')

        query = EquipmentMaintenance.query
        if equipment_id:
            query = query.filter_by(equipment_id=equipment_id)
        if maintenance_type:
            query = query.filter_by(maintenance_type=maintenance_type)

        records = query.order_by(EquipmentMaintenance.maintenance_date.desc()).all()
        return jsonify([r.to_dict() for r in records])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# ASSIGNMENT ROUTES
# ============================================

@equipment_bp.route('/assignments', methods=['GET'])
def get_all_assignments():
    """Get all equipment assignments (most recent first)."""
    try:
        equipment_id = request.args.get('equipmentId')
        query = EquipmentAssignment.query
        if equipment_id:
            query = query.filter_by(equipment_id=equipment_id)
        rows = query.order_by(EquipmentAssignment.assigned_date.desc()).all()
        return jsonify([r.to_dict() for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@equipment_bp.route('/<equipment_id>/assign', methods=['POST'])
def assign_equipment(equipment_id):
    """
    Assign equipment to a site or a worker.

    Body:
      {
        "assignedToType": "site" | "worker",
        "assignedToId": "<site-or-worker-id>",
        "siteId": "<site-id>",         # optional, if assignedToType=site
        "workerId": "<worker-id>",     # optional, if assignedToType=worker
        "assignedDate": "YYYY-MM-DD",
        "expectedReturnDate": "YYYY-MM-DD" | null,
        "notes": "..."
      }

    Behaviour:
      - Closes any existing open assignment for this equipment.
      - Creates a new assignment.
      - Updates equipment.status, site_id, assigned_to_worker_id.
    """
    try:
        data = request.json or {}
        equipment = Equipment.query.get_or_404(equipment_id)

        assigned_to_type = data.get('assignedToType', 'site')
        assigned_to_id = data.get('assignedToId')
        site_id = data.get('siteId') if assigned_to_type == 'site' else None
        worker_id = data.get('workerId') if assigned_to_type == 'worker' else None

        # Fallback: derive assigned_to_id from siteId/workerId if not provided
        if not assigned_to_id:
            assigned_to_id = site_id if assigned_to_type == 'site' else worker_id

        if not assigned_to_id:
            return jsonify({'error': 'assignedToId (or siteId/workerId) is required'}), 400

        assigned_date = _parse_date(data.get('assignedDate')) or datetime.now().date()

        # Close any existing open assignment
        EquipmentAssignment.query.filter_by(
            equipment_id=equipment_id,
            actual_return_date=None
        ).update({'actual_return_date': assigned_date})

        assignment = EquipmentAssignment(
            id=generate_id(),
            equipment_id=equipment_id,
            assigned_to_type=assigned_to_type,
            assigned_to_id=assigned_to_id,
            assigned_date=assigned_date,
            expected_return_date=_parse_date(data.get('expectedReturnDate')),
            notes=data.get('notes')
        )
        db.session.add(assignment)

        # Update equipment state
        if assigned_to_type == 'site':
            equipment.site_id = site_id or assigned_to_id
            equipment.assigned_to_worker_id = None
        else:
            equipment.assigned_to_worker_id = worker_id or assigned_to_id
            # If the worker is on a site, optionally keep the equipment's site_id from payload
            if site_id:
                equipment.site_id = site_id

        equipment.status = 'assigned'

        db.session.commit()
        return jsonify(assignment.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in assign_equipment: {str(e)}")
        return jsonify({'error': str(e)}), 400


@equipment_bp.route('/<equipment_id>/return', methods=['PUT'])
def return_equipment(equipment_id):
    """
    Return equipment from its current assignment.

    Body:
      {
        "actualReturnDate": "YYYY-MM-DD",
        "conditionOnReturn": "good" | "fair" | ... ,
        "notes": "..."
      }
    """
    try:
        data = request.json or {}
        equipment = Equipment.query.get_or_404(equipment_id)

        active = EquipmentAssignment.query.filter_by(
            equipment_id=equipment_id,
            actual_return_date=None
        ).first()

        if active:
            active.actual_return_date = _parse_date(data.get('actualReturnDate')) or datetime.now().date()
            active.condition_on_return = data.get('conditionOnReturn') or equipment.condition
            if data.get('notes'):
                active.notes = ((active.notes or '') + '\n' + data['notes']).strip()

        # Reset equipment state
        equipment.site_id = None
        equipment.assigned_to_worker_id = None
        equipment.status = 'available'
        if data.get('conditionOnReturn'):
            equipment.condition = data['conditionOnReturn']

        db.session.commit()
        return jsonify(equipment.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error in return_equipment: {str(e)}")
        return jsonify({'error': str(e)}), 400


# ============================================
# USAGE ROUTES
# ============================================

@equipment_bp.route('/usage', methods=['GET'])
def get_all_usage():
    """Get all usage records (most recent first)."""
    try:
        equipment_id = request.args.get('equipmentId')
        query = EquipmentUsage.query
        if equipment_id:
            query = query.filter_by(equipment_id=equipment_id)
        rows = query.order_by(EquipmentUsage.date.desc()).all()
        return jsonify([r.to_dict() for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@equipment_bp.route('/<equipment_id>/usage', methods=['POST'])
def log_usage(equipment_id):
    """Log equipment usage"""
    try:
        data = request.json

        usage = EquipmentUsage(
            id=generate_id(),
            equipment_id=equipment_id,
            date=_parse_date(data.get('date')) or datetime.now().date(),
            hours_used=float(data.get('hoursUsed') or 0),
            fuel_used=float(data.get('fuelUsed') or 0),
            fuel_cost=float(data.get('fuelCost') or 0),
            operator_name=data.get('operatorName'),
            site_id=data.get('siteId'),
            project_id=data.get('projectId'),
            notes=data.get('notes')
        )

        equipment = Equipment.query.get(equipment_id)
        if equipment:
            equipment.total_hours_used = (equipment.total_hours_used or 0) + usage.hours_used

        db.session.add(usage)
        db.session.commit()

        return jsonify(usage.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ============================================
# CATEGORY ROUTES
# ============================================

@equipment_bp.route('/categories', methods=['GET'])
def get_categories():
    try:
        categories = EquipmentCategory.query.all()
        return jsonify([c.to_dict() for c in categories])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# SUMMARY
# ============================================

@equipment_bp.route('/summary', methods=['GET'])
def get_equipment_summary():
    try:
        total = Equipment.query.count()
        available = Equipment.query.filter_by(status='available').count()
        assigned = Equipment.query.filter_by(status='assigned').count()
        maintenance = Equipment.query.filter_by(status='maintenance').count()
        repair = Equipment.query.filter_by(status='repair').count()

        total_value = db.session.query(db.func.sum(Equipment.current_value)).scalar() or 0

        today = datetime.now().date()
        needs_maintenance = Equipment.query.filter(
            Equipment.next_maintenance_date <= today + timedelta(days=7),
            Equipment.status.in_(['available', 'assigned'])
        ).count()

        # NEW: on-site count
        on_site = Equipment.query.filter(Equipment.site_id.isnot(None)).count()

        return jsonify({
            'total': total,
            'available': available,
            'assigned': assigned,
            'onSite': on_site,
            'maintenance': maintenance,
            'repair': repair,
            'totalValue': total_value,
            'needsMaintenance': needs_maintenance
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# DEPRECIATION
# ============================================

@equipment_bp.route('/<equipment_id>/depreciation', methods=['POST'])
def calculate_depreciation(equipment_id):
    try:
        equipment = Equipment.query.get_or_404(equipment_id)

        monthly_depreciation = equipment.calculate_depreciation()
        current_value = equipment.current_value - monthly_depreciation

        depreciation = EquipmentDepreciation(
            id=generate_id(),
            equipment_id=equipment_id,
            period_date=datetime.now().date(),
            period_type='monthly',
            beginning_value=equipment.current_value,
            depreciation_amount=monthly_depreciation,
            ending_value=current_value,
            accumulated_depreciation=(equipment.purchase_price or 0) - current_value
        )

        equipment.current_value = max(current_value, equipment.salvage_value or 0)

        db.session.add(depreciation)
        db.session.commit()

        return jsonify(depreciation.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400