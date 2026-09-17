# routes/units.py
from datetime import datetime
from flask import request, jsonify
from models import db, Unit
from utils.helpers import generate_id
from routes import units_bp


# ============================================
# GET /api/units   — list (with optional filters)
# ============================================
@units_bp.route('', methods=['GET'])
def list_units():
    try:
        q = Unit.query

        # By default, only show active ones. Pass ?includeInactive=1 for all.
        include_inactive = request.args.get('includeInactive') in ('1', 'true', 'yes')
        if not include_inactive:
            q = q.filter(Unit.is_active.is_(True))

        category = request.args.get('category')
        if category and category != 'all':
            q = q.filter(Unit.category == category)

        search = request.args.get('search')
        if search:
            like = f'%{search}%'
            q = q.filter(db.or_(
                Unit.name.ilike(like),
                Unit.symbol.ilike(like),
                Unit.category.ilike(like),
            ))

        rows = q.order_by(Unit.sort_order.asc(), Unit.name.asc()).all()
        return jsonify([r.to_dict() for r in rows])
    except Exception as e:
        print(f'Error in list_units: {e}')
        return jsonify({'error': str(e)}), 500


# ============================================
# GET /api/units/categories  — distinct categories
# ============================================
@units_bp.route('/categories', methods=['GET'])
def list_unit_categories():
    try:
        rows = db.session.query(Unit.category).distinct().all()
        cats = sorted({(r[0] or 'General') for r in rows})
        return jsonify(cats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# POST /api/units   — create
# ============================================
@units_bp.route('', methods=['POST'])
def create_unit():
    try:
        data = request.json or {}
        name = (data.get('name') or '').strip().upper()

        if not name:
            return jsonify({'error': 'Unit name is required'}), 400

        if Unit.query.filter(db.func.upper(Unit.name) == name).first():
            return jsonify({'error': f'Unit "{name}" already exists'}), 409

        max_order = db.session.query(db.func.coalesce(db.func.max(Unit.sort_order), 0)).scalar() or 0

        rec = Unit(
            id=generate_id(),
            name=name,
            symbol=(data.get('symbol') or '').strip(),
            category=(data.get('category') or 'General').strip(),
            is_active=data.get('isActive', True),
            sort_order=int(data.get('sortOrder') or (max_order + 1)),
        )
        db.session.add(rec)
        db.session.commit()
        return jsonify(rec.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f'Error in create_unit: {e}')
        return jsonify({'error': str(e)}), 400


# ============================================
# PUT /api/units/<id>   — update
# ============================================
@units_bp.route('/<unit_id>', methods=['PUT'])
def update_unit(unit_id):
    try:
        rec = Unit.query.get(unit_id)
        if not rec:
            return jsonify({'error': 'Unit not found'}), 404

        data = request.json or {}

        if 'name' in data:
            new_name = (data['name'] or '').strip().upper()
            if not new_name:
                return jsonify({'error': 'Unit name cannot be empty'}), 400
            dup = Unit.query.filter(
                db.func.upper(Unit.name) == new_name,
                Unit.id != unit_id
            ).first()
            if dup:
                return jsonify({'error': f'Unit "{new_name}" already exists'}), 409
            rec.name = new_name

        if 'symbol' in data:      rec.symbol = (data['symbol'] or '').strip()
        if 'category' in data:    rec.category = (data['category'] or 'General').strip()
        if 'isActive' in data:    rec.is_active = bool(data['isActive'])
        if 'sortOrder' in data:   rec.sort_order = int(data['sortOrder'] or 0)

        db.session.commit()
        return jsonify(rec.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ============================================
# DELETE /api/units/<id>
# ============================================
@units_bp.route('/<unit_id>', methods=['DELETE'])
def delete_unit(unit_id):
    try:
        rec = Unit.query.get(unit_id)
        if not rec:
            return jsonify({'error': 'Unit not found'}), 404
        db.session.delete(rec)
        db.session.commit()
        return jsonify({'message': 'Deleted'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400