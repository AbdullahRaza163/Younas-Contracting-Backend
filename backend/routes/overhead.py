from flask import request, jsonify
from models import MonthlyOverhead, OverheadCategory, Site, db
from utils.helpers import generate_id
from routes import overhead_bp
import json

# Monthly Overhead Routes
@overhead_bp.route('/monthly-overhead', methods=['GET'])
def get_monthly_overhead():
    """Get monthly overhead records"""
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
        
        overheads = query.order_by(MonthlyOverhead.month.desc(), MonthlyOverhead.category_name).all()
        return jsonify([o.to_dict() for o in overheads])
    except Exception as e:
        print(f"Error in get_monthly_overhead: {str(e)}")
        return jsonify({'error': str(e)}), 500


@overhead_bp.route('/monthly-overhead', methods=['POST'])
def create_monthly_overhead():
    """Create a new monthly overhead record"""
    try:
        data = request.json
        print(f"Received monthly overhead data: {data}")
        
        if not data.get('month'):
            return jsonify({'error': 'Month is required'}), 400
        
        # Handle category
        category_id = data.get('categoryId')
        category_name = data.get('categoryName')
        
        if category_id:
            category = OverheadCategory.query.get(category_id)
            if category:
                category_name = category.name
            else:
                return jsonify({'error': 'Category not found'}), 404
        elif category_name:
            category = OverheadCategory.query.filter_by(name=category_name).first()
            if not category:
                category = OverheadCategory(
                    id=generate_id(),
                    name=category_name,
                    type='company',
                    is_recurring=True,
                    default_frequency='monthly',
                    is_active=True
                )
                db.session.add(category)
                db.session.commit()
                category_id = category.id
            else:
                category_id = category.id
        else:
            return jsonify({'error': 'Category ID or Name is required'}), 400
        
        # Handle site_id
        site_id = data.get('siteId')
        if site_id == '' or site_id == 'null' or site_id is None:
            site_id = None
        
        # Handle site_names
        site_names = data.get('siteNames', [])
        sites_count = data.get('sitesCount', 1)
        
        # Calculate sites_count if not provided
        if not sites_count or sites_count == 0:
            if site_id:
                sites_count = 1
            else:
                # Count active sites
                sites_count = Site.query.filter_by(active=True).count() or 1
        
        # Convert site_names to JSON string for storage
        site_names_json = json.dumps(site_names) if site_names else None
        
        # Check if entry exists (same month, category, and site)
        query = MonthlyOverhead.query.filter_by(
            month=data.get('month'),
            category_id=category_id
        )
        if site_id:
            query = query.filter_by(site_id=site_id)
        else:
            query = query.filter_by(site_id=None)
        
        existing = query.first()
        
        if existing:
            # Update existing entry
            existing.amount = float(data.get('amount', 0))
            existing.sites_count = int(sites_count)
            existing.working_days = int(data.get('workingDays', 26))
            existing.notes = data.get('notes', '')
            existing.category_name = category_name
            existing.site_names = site_names_json
            db.session.commit()
            print(f"✅ Updated existing overhead: {existing.to_dict()}")
            return jsonify(existing.to_dict()), 200
        
        # Create new entry
        overhead = MonthlyOverhead(
            id=generate_id(),
            month=data.get('month'),
            category_id=category_id,
            category_name=category_name,
            amount=float(data.get('amount', 0)),
            site_id=site_id,
            site_names=site_names_json,
            sites_count=int(sites_count),
            working_days=int(data.get('workingDays', 26)),
            notes=data.get('notes', '')
        )
        
        db.session.add(overhead)
        db.session.commit()
        print(f"✅ Created new overhead: {overhead.to_dict()}")
        return jsonify(overhead.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in create_monthly_overhead: {str(e)}")
        return jsonify({'error': str(e)}), 400


@overhead_bp.route('/monthly-overhead/<overhead_id>', methods=['GET'])
def get_monthly_overhead_by_id(overhead_id):
    """Get a specific monthly overhead record"""
    try:
        overhead = MonthlyOverhead.query.get_or_404(overhead_id)
        return jsonify(overhead.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@overhead_bp.route('/monthly-overhead/<overhead_id>', methods=['PUT'])
def update_monthly_overhead(overhead_id):
    """Update a monthly overhead record"""
    try:
        overhead = MonthlyOverhead.query.get_or_404(overhead_id)
        data = request.json
        
        print(f"Updating overhead {overhead_id} with data: {data}")
        
        if 'month' in data and data['month']:
            overhead.month = data['month']
        if 'categoryId' in data:
            category = OverheadCategory.query.get(data['categoryId'])
            if category:
                overhead.category_id = data['categoryId']
                overhead.category_name = category.name
        if 'categoryName' in data:
            overhead.category_name = data['categoryName']
        if 'amount' in data:
            overhead.amount = float(data['amount'])
        if 'siteId' in data:
            site_id = data.get('siteId')
            if site_id == '' or site_id == 'null' or site_id is None:
                overhead.site_id = None
            else:
                overhead.site_id = site_id
        if 'siteNames' in data:
            site_names = data.get('siteNames', [])
            overhead.site_names = json.dumps(site_names) if site_names else None
        if 'sitesCount' in data:
            overhead.sites_count = int(data.get('sitesCount', 1))
        if 'workingDays' in data:
            overhead.working_days = int(data.get('workingDays', 26))
        if 'notes' in data:
            overhead.notes = data.get('notes', '')
        
        db.session.commit()
        print(f"✅ Updated overhead: {overhead.to_dict()}")
        return jsonify(overhead.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in update_monthly_overhead: {str(e)}")
        return jsonify({'error': str(e)}), 400


@overhead_bp.route('/monthly-overhead/<overhead_id>', methods=['DELETE'])
def delete_monthly_overhead(overhead_id):
    """Delete a monthly overhead record"""
    try:
        overhead = MonthlyOverhead.query.get_or_404(overhead_id)
        print(f"🗑️ Deleting overhead: {overhead.to_dict()}")
        db.session.delete(overhead)
        db.session.commit()
        return jsonify({'message': 'Monthly overhead deleted successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in delete_monthly_overhead: {str(e)}")
        return jsonify({'error': str(e)}), 400


# Overhead Categories Routes
@overhead_bp.route('/overhead-categories', methods=['GET'])
def get_overhead_categories():
    """Get all overhead categories"""
    try:
        categories = OverheadCategory.query.filter_by(is_active=True).order_by(OverheadCategory.name).all()
        return jsonify([c.to_dict() for c in categories])
    except Exception as e:
        print(f"Error in get_overhead_categories: {str(e)}")
        return jsonify({'error': str(e)}), 500


@overhead_bp.route('/overhead-categories', methods=['POST'])
def create_overhead_category():
    """Create a new overhead category"""
    try:
        data = request.json
        category = OverheadCategory(
            id=generate_id(),
            name=data.get('name'),
            type=data.get('type', 'company'),
            is_recurring=data.get('isRecurring', True),
            default_frequency=data.get('defaultFrequency', 'monthly'),
            gl_account=data.get('glAccount', ''),
            is_active=True
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
    """Update an overhead category"""
    try:
        category = OverheadCategory.query.get_or_404(category_id)
        data = request.json
        
        category.name = data.get('name', category.name)
        category.type = data.get('type', category.type)
        category.is_recurring = data.get('isRecurring', category.is_recurring)
        category.default_frequency = data.get('defaultFrequency', category.default_frequency)
        category.gl_account = data.get('glAccount', category.gl_account)
        category.is_active = data.get('isActive', category.is_active)
        
        db.session.commit()
        return jsonify(category.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@overhead_bp.route('/overhead-categories/<category_id>', methods=['DELETE'])
def delete_overhead_category(category_id):
    """Delete an overhead category"""
    try:
        category = OverheadCategory.query.get_or_404(category_id)
        db.session.delete(category)
        db.session.commit()
        return jsonify({'message': 'Category deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400