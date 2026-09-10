from flask import request, jsonify
from models import Site, db
from utils.helpers import generate_id
from routes import sites_bp

@sites_bp.route('', methods=['GET'])
def get_sites():
    """Get all active sites"""
    try:
        sites = Site.query.filter_by(active=True).order_by(Site.created_at.desc()).all()
        return jsonify([s.to_dict() for s in sites])
    except Exception as e:
        print(f"Error in get_sites: {str(e)}")
        return jsonify({'error': str(e)}), 500

@sites_bp.route('/all', methods=['GET'])
def get_all_sites_including_inactive():
    """Get all sites including inactive ones"""
    try:
        sites = Site.query.order_by(Site.created_at.desc()).all()
        return jsonify([s.to_dict() for s in sites])
    except Exception as e:
        print(f"Error in get_all_sites: {str(e)}")
        return jsonify({'error': str(e)}), 500

@sites_bp.route('', methods=['POST'])
def create_site():
    """Create a new site"""
    try:
        data = request.json
        site = Site(
            id=generate_id(),
            name=data.get('name'),
            location=data.get('location', ''),
            manager=data.get('manager', ''),
            manager_salary=float(data.get('managerSalary', 0)),
            phone=data.get('phone', ''),
            active=True
        )
        db.session.add(site)
        db.session.commit()
        return jsonify(site.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@sites_bp.route('/<site_id>', methods=['GET'])
def get_site(site_id):
    """Get a specific site by ID"""
    try:
        site = Site.query.get_or_404(site_id)
        return jsonify(site.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@sites_bp.route('/<site_id>', methods=['PUT'])
def update_site(site_id):
    """Update a site"""
    try:
        site = Site.query.get_or_404(site_id)
        data = request.json
        
        site.name = data.get('name', site.name)
        site.location = data.get('location', site.location)
        site.manager = data.get('manager', site.manager)
        site.manager_salary = float(data.get('managerSalary', site.manager_salary))
        site.phone = data.get('phone', site.phone)
        site.active = data.get('active', site.active)
        
        db.session.commit()
        return jsonify(site.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@sites_bp.route('/<site_id>', methods=['DELETE'])
def delete_site(site_id):
    """Soft delete a site (set inactive)"""
    try:
        site = Site.query.get_or_404(site_id)
        site.active = False
        db.session.commit()
        return jsonify({'message': 'Site deactivated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@sites_bp.route('/<site_id>/permanent', methods=['DELETE'])
def permanent_delete_site(site_id):
    """Permanently delete a site"""
    try:
        site = Site.query.get_or_404(site_id)
        db.session.delete(site)
        db.session.commit()
        return jsonify({'message': 'Site permanently deleted'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400