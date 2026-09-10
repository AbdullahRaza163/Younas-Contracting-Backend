from flask import request, jsonify
from models import Item, db
from utils.helpers import generate_id
from routes import items_bp

@items_bp.route('', methods=['GET'])
def get_items():
    """Get all active items"""
    try:
        category = request.args.get('category')
        query = Item.query.filter_by(is_active=True)
        if category:
            query = query.filter_by(category=category)
        items = query.order_by(Item.name.asc()).all()
        return jsonify([i.to_dict() for i in items])
    except Exception as e:
        print(f"Error in get_items: {str(e)}")
        return jsonify({'error': str(e)}), 500

@items_bp.route('/all', methods=['GET'])
def get_all_items():
    """Get all items including inactive"""
    try:
        items = Item.query.order_by(Item.name.asc()).all()
        return jsonify([i.to_dict() for i in items])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@items_bp.route('', methods=['POST'])
def create_item():
    """Create a new item"""
    try:
        data = request.json
        item = Item(
            id=generate_id(),
            name=data.get('name'),
            category=data.get('category'),
            unit=data.get('unit'),
            unit_price=float(data.get('unitPrice', 0)),
            description=data.get('description', ''),
            sku=data.get('sku', ''),
            tax_rate=float(data.get('taxRate', 0)),
            is_taxable=data.get('isTaxable', False),
            quantity=float(data.get('quantity', 0)),
            reorder_level=float(data.get('reorderLevel', 0)),
            supplier=data.get('supplier', ''),
            is_active=True
        )
        db.session.add(item)
        db.session.commit()
        return jsonify(item.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_item: {str(e)}")
        return jsonify({'error': str(e)}), 400

@items_bp.route('/<item_id>', methods=['GET'])
def get_item(item_id):
    """Get a specific item"""
    try:
        item = Item.query.get_or_404(item_id)
        return jsonify(item.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@items_bp.route('/<item_id>', methods=['PUT'])
def update_item(item_id):
    """Update an item"""
    try:
        item = Item.query.get_or_404(item_id)
        data = request.json
        
        item.name = data.get('name', item.name)
        item.category = data.get('category', item.category)
        item.unit = data.get('unit', item.unit)
        item.unit_price = float(data.get('unitPrice', item.unit_price))
        item.description = data.get('description', item.description)
        item.sku = data.get('sku', item.sku)
        item.tax_rate = float(data.get('taxRate', item.tax_rate))
        item.is_taxable = data.get('isTaxable', item.is_taxable)
        item.quantity = float(data.get('quantity', item.quantity))
        item.reorder_level = float(data.get('reorderLevel', item.reorder_level))
        item.supplier = data.get('supplier', item.supplier)
        item.is_active = data.get('isActive', item.is_active)
        
        db.session.commit()
        return jsonify(item.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@items_bp.route('/<item_id>', methods=['DELETE'])
def delete_item(item_id):
    """Soft delete an item"""
    try:
        item = Item.query.get_or_404(item_id)
        item.is_active = False
        db.session.commit()
        return jsonify({'message': 'Item deactivated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@items_bp.route('/<item_id>/stock', methods=['PUT'])
def update_item_stock(item_id):
    """Update item stock quantity"""
    try:
        item = Item.query.get_or_404(item_id)
        data = request.json
        quantity_change = float(data.get('quantityChange', 0))
        item.update_stock(quantity_change)
        db.session.commit()
        return jsonify(item.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@items_bp.route('/low-stock', methods=['GET'])
def get_low_stock_items():
    """Get all items that are low on stock"""
    try:
        items = Item.get_low_stock_items()
        return jsonify([i.to_dict() for i in items])
    except Exception as e:
        return jsonify({'error': str(e)}), 500