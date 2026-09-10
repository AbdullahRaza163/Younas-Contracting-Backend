from flask import request, jsonify
from models import Setting, db
from routes import settings_bp
import json

@settings_bp.route('', methods=['GET'])
def get_settings():
    """Get all settings"""
    try:
        settings = Setting.query.all()
        result = {}
        for s in settings:
            try:
                result[s.key] = json.loads(s.value) if s.value else None
            except:
                result[s.key] = s.value
        return jsonify(result)
    except Exception as e:
        print(f"Error in get_settings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@settings_bp.route('/<key>', methods=['GET'])
def get_setting(key):
    """Get a specific setting by key"""
    try:
        setting = Setting.query.filter_by(key=key).first()
        if not setting:
            return jsonify({'error': 'Setting not found'}), 404
        
        try:
            value = json.loads(setting.value) if setting.value else None
        except:
            value = setting.value
        
        return jsonify({key: value})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@settings_bp.route('', methods=['POST'])
def create_or_update_setting():
    """Create or update a setting"""
    try:
        data = request.json
        key = data.get('key')
        value = data.get('value')
        category = data.get('category', 'general')
        
        if not key:
            return jsonify({'error': 'Key is required'}), 400
        
        setting = Setting.set_setting(key, value, category)
        return jsonify(setting.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_or_update_setting: {str(e)}")
        return jsonify({'error': str(e)}), 400

@settings_bp.route('/<key>', methods=['PUT'])
def update_setting(key):
    """Update a specific setting"""
    try:
        data = request.json
        value = data.get('value')
        category = data.get('category', 'general')
        
        setting = Setting.set_setting(key, value, category)
        return jsonify(setting.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@settings_bp.route('/<key>', methods=['DELETE'])
def delete_setting(key):
    """Delete a setting"""
    try:
        setting = Setting.query.filter_by(key=key).first()
        if not setting:
            return jsonify({'error': 'Setting not found'}), 404
        
        db.session.delete(setting)
        db.session.commit()
        return jsonify({'message': f'Setting {key} deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@settings_bp.route('/category/<category>', methods=['GET'])
def get_settings_by_category(category):
    """Get all settings in a category"""
    try:
        settings = Setting.query.filter_by(category=category).all()
        result = {}
        for s in settings:
            try:
                result[s.key] = json.loads(s.value) if s.value else None
            except:
                result[s.key] = s.value
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500