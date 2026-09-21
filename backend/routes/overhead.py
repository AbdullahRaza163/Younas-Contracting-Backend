# routes/overhead.py
from flask import request, jsonify
from models import MonthlyOverhead, OverheadCategory, Site, db
from utils.helpers import generate_id
from routes import overhead_bp
import json


# ============================================
# MONTHLY OVERHEAD
# ============================================

@overhead_bp.route('/monthly-overhead', methods=['GET'])
def get_monthly_overhead():
    try:
        month = request.args.get('month')
        site_id = request.args.get('siteId')

        query = MonthlyOverhead.query
        if month:
            query = query.filter_by(month=month)
        if site_id:
            query = query.filter(
                (MonthlyOverhead.site_id == site_id) |
                (MonthlyOverhead.site_id.is_(None))
            )

        overheads = query.order_by(
            MonthlyOverhead.month.desc(),
            MonthlyOverhead.category_name
        ).all()
        return jsonify([o.to_dict() for o in overheads])
    except Exception as e:
        print(f"Error in get_monthly_overhead: {str(e)}")
        return jsonify({'error': str(e)}), 500


@overhead_bp.route('/monthly-overhead', methods=['POST'])
def create_monthly_overhead():
    try:
        data = request.json
        if not data.get('month'):
            return jsonify({'error': 'Month is required'}), 400

        # Resolve category
        category_id = data.get('categoryId')
        category_name = data.get('categoryName')
        category_frequency = 'monthly'

        if category_id:
            category = OverheadCategory.query.get(category_id)
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            category_name = category.name
            category_frequency = category.default_frequency or 'monthly'
        elif category_name:
            category = OverheadCategory.query.filter_by(name=category_name).first()
            if not category:
                category = OverheadCategory(
                    id=generate_id(), name=category_name,
                    type='company', is_recurring=True,
                    default_frequency='monthly', is_active=True,
                )
                db.session.add(category)
                db.session.flush()
            category_id = category.id
            category_frequency = category.default_frequency or 'monthly'
        else:
            return jsonify({'error': 'Category ID or Name is required'}), 400

        # Site
        site_id = data.get('siteId')
        if site_id in ('', 'null', None):
            site_id = None

        site_names = data.get('siteNames', [])
        sites_count = int(data.get('sitesCount') or 1)
        if sites_count <= 0:
            sites_count = 1 if site_id else (Site.query.filter_by(active=True).count() or 1)

        # ⭐ Frequency: prefer explicit, else use category default
        frequency = data.get('frequency') or category_frequency

        existing = MonthlyOverhead.query.filter_by(
            month=data['month'], category_id=category_id, site_id=site_id
        ).first()

        if existing:
            existing.amount = float(data.get('amount', 0))
            existing.sites_count = sites_count
            existing.working_days = int(data.get('workingDays', 26))
            existing.notes = data.get('notes', '')
            existing.category_name = category_name
            existing.frequency = frequency
            existing.site_names = json.dumps(site_names) if site_names else None
            db.session.commit()
            return jsonify(existing.to_dict()), 200

        overhead = MonthlyOverhead(
            id=generate_id(),
            month=data['month'],
            category_id=category_id,
            category_name=category_name,
            amount=float(data.get('amount', 0)),
            frequency=frequency,
            site_id=site_id,
            site_names=json.dumps(site_names) if site_names else None,
            sites_count=sites_count,
            working_days=int(data.get('workingDays', 26)),
            notes=data.get('notes', ''),
        )
        db.session.add(overhead)
        db.session.commit()
        return jsonify(overhead.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_monthly_overhead: {str(e)}")
        return jsonify({'error': str(e)}), 400


@overhead_bp.route('/monthly-overhead/<overhead_id>', methods=['GET'])
def get_monthly_overhead_by_id(overhead_id):
    try:
        o = MonthlyOverhead.query.get_or_404(overhead_id)
        return jsonify(o.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@overhead_bp.route('/monthly-overhead/<overhead_id>', methods=['PUT'])
def update_monthly_overhead(overhead_id):
    try:
        o = MonthlyOverhead.query.get_or_404(overhead_id)
        data = request.json or {}

        if 'month' in data and data['month']:
            o.month = data['month']
        if 'categoryId' in data:
            cat = OverheadCategory.query.get(data['categoryId'])
            if cat:
                o.category_id = data['categoryId']
                o.category_name = cat.name
        if 'categoryName' in data:
            o.category_name = data['categoryName']
        if 'amount' in data:
            o.amount = float(data['amount'] or 0)
        if 'frequency' in data and data['frequency']:
            o.frequency = data['frequency']
        if 'siteId' in data:
            sid = data.get('siteId')
            o.site_id = None if sid in ('', 'null', None) else sid
        if 'siteNames' in data:
            names = data.get('siteNames', [])
            o.site_names = json.dumps(names) if names else None
        if 'sitesCount' in data:
            o.sites_count = int(data.get('sitesCount') or 1)
        if 'workingDays' in data:
            o.working_days = int(data.get('workingDays') or 26)
        if 'notes' in data:
            o.notes = data.get('notes', '')

        db.session.commit()
        return jsonify(o.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_monthly_overhead: {str(e)}")
        return jsonify({'error': str(e)}), 400


@overhead_bp.route('/monthly-overhead/<overhead_id>', methods=['DELETE'])
def delete_monthly_overhead(overhead_id):
    try:
        o = MonthlyOverhead.query.get_or_404(overhead_id)
        db.session.delete(o)
        db.session.commit()
        return jsonify({'message': 'Monthly overhead deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ============================================
# OVERHEAD CATEGORIES  ⭐ simple templates
# ============================================

@overhead_bp.route('/overhead-categories', methods=['GET'])
def get_overhead_categories():
    try:
        include_inactive = request.args.get('includeInactive', 'false').lower() == 'true'
        query = OverheadCategory.query
        if not include_inactive:
            query = query.filter_by(is_active=True)
        categories = query.order_by(OverheadCategory.name).all()
        return jsonify([c.to_dict() for c in categories])
    except Exception as e:
        print(f"Error in get_overhead_categories: {str(e)}")
        return jsonify({'error': str(e)}), 500


@overhead_bp.route('/overhead-categories', methods=['POST'])
def create_overhead_category():
    """Create a category template. NO auto-creation of monthly entries."""
    try:
        data = request.json or {}

        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': 'Category name is required'}), 400

        existing = OverheadCategory.query.filter_by(name=name).first()
        if existing:
            return jsonify({'error': f"Category '{name}' already exists"}), 400

        category = OverheadCategory(
            id=generate_id(),
            name=name,
            type=data.get('type', 'company'),
            is_recurring=bool(data.get('isRecurring', True)),
            default_frequency=data.get('defaultFrequency', 'monthly'),
            default_amount=float(data.get('defaultAmount', 0) or 0),   # ⭐ NEW
            gl_account=data.get('glAccount', ''),
            is_active=True,
        )
        db.session.add(category)
        db.session.commit()

        return jsonify(category.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_overhead_category: {str(e)}")
        return jsonify({'error': str(e)}), 400


@overhead_bp.route('/overhead-categories/<category_id>', methods=['PUT'])
def update_overhead_category(category_id):
    """
    Update a category template.
    Syncs the new name + frequency to existing entries only.
    Does NOT auto-create new entries.
    """
    try:
        category = OverheadCategory.query.get_or_404(category_id)
        data = request.json or {}

        new_name = (data.get('name') or category.name).strip()
        if new_name != category.name:
            dup = OverheadCategory.query.filter_by(name=new_name).first()
            if dup and dup.id != category.id:
                return jsonify({'error': f"Category '{new_name}' already exists"}), 400

        category.name = new_name
        category.type = data.get('type', category.type)
        category.is_recurring = bool(data.get('isRecurring', category.is_recurring))
        category.default_frequency = data.get('defaultFrequency', category.default_frequency)
        category.default_amount = float(data.get('defaultAmount', category.default_amount) or 0)
        category.gl_account = data.get('glAccount', category.gl_account)
        category.is_active = bool(data.get('isActive', category.is_active))

        # Sync name + frequency to existing entries (denormalized fields)
        synced = 0
        for entry in category.monthly_overheads or []:
            entry.category_name = category.name
            entry.frequency = category.default_frequency
            synced += 1

        db.session.commit()

        response = category.to_dict()
        response['syncedEntries'] = synced
        return jsonify(response)
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_overhead_category: {str(e)}")
        return jsonify({'error': str(e)}), 400


@overhead_bp.route('/overhead-categories/<category_id>', methods=['DELETE'])
def delete_overhead_category(category_id):
    try:
        category = OverheadCategory.query.get_or_404(category_id)
        keep = request.args.get('keepEntries', 'false').lower() == 'true'

        if keep:
            for entry in list(category.monthly_overheads or []):
                entry.category_id = None
            db.session.flush()

        db.session.delete(category)
        db.session.commit()
        return jsonify({'message': 'Category deleted successfully', 'keptEntries': keep})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400