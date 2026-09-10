# routes/inventory.py
from flask import request, jsonify
from models import db, Material, MaterialCategory, Supplier, PurchaseOrder, PurchaseOrderItem, StockMovement
from utils.helpers import generate_id
from routes import inventory_bp
from datetime import datetime
import random
import string

# ============================================
# MATERIAL CATEGORIES
# ============================================

@inventory_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get all material categories"""
    try:
        categories = MaterialCategory.query.all()
        return jsonify([c.to_dict() for c in categories])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@inventory_bp.route('/categories', methods=['POST'])
def create_category():
    """Create a new material category"""
    try:
        data = request.json
        category = MaterialCategory(
            id=generate_id(),
            name=data.get('name'),
            description=data.get('description'),
            icon=data.get('icon')
        )
        db.session.add(category)
        db.session.commit()
        return jsonify(category.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@inventory_bp.route('/categories/<category_id>', methods=['PUT'])
def update_category(category_id):
    """Update a material category"""
    try:
        category = MaterialCategory.query.get_or_404(category_id)
        data = request.json
        
        if 'name' in data:
            category.name = data['name']
        if 'description' in data:
            category.description = data['description']
        if 'icon' in data:
            category.icon = data['icon']
        
        db.session.commit()
        return jsonify(category.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@inventory_bp.route('/categories/<category_id>', methods=['DELETE'])
def delete_category(category_id):
    """Delete a material category"""
    try:
        category = MaterialCategory.query.get_or_404(category_id)
        db.session.delete(category)
        db.session.commit()
        return jsonify({'message': 'Category deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# SUPPLIERS
# ============================================

@inventory_bp.route('/suppliers', methods=['GET'])
def get_suppliers():
    """Get all suppliers"""
    try:
        suppliers = Supplier.query.all()
        return jsonify([s.to_dict() for s in suppliers])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@inventory_bp.route('/suppliers', methods=['POST'])
def create_supplier():
    """Create a new supplier"""
    try:
        data = request.json
        supplier = Supplier(
            id=generate_id(),
            name=data.get('name'),
            contact_person=data.get('contactPerson'),
            email=data.get('email'),
            phone=data.get('phone'),
            mobile=data.get('mobile'),
            address=data.get('address'),
            city=data.get('city'),
            country=data.get('country'),
            cr_number=data.get('crNumber'),
            vat_number=data.get('vatNumber'),
            payment_terms=data.get('paymentTerms'),
            rating=int(data.get('rating', 3)),
            notes=data.get('notes')
        )
        db.session.add(supplier)
        db.session.commit()
        return jsonify(supplier.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@inventory_bp.route('/suppliers/<supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    """Update a supplier"""
    try:
        supplier = Supplier.query.get_or_404(supplier_id)
        data = request.json
        
        if 'name' in data:
            supplier.name = data['name']
        if 'contactPerson' in data:
            supplier.contact_person = data['contactPerson']
        if 'email' in data:
            supplier.email = data['email']
        if 'phone' in data:
            supplier.phone = data['phone']
        if 'mobile' in data:
            supplier.mobile = data['mobile']
        if 'address' in data:
            supplier.address = data['address']
        if 'city' in data:
            supplier.city = data['city']
        if 'country' in data:
            supplier.country = data['country']
        if 'crNumber' in data:
            supplier.cr_number = data['crNumber']
        if 'vatNumber' in data:
            supplier.vat_number = data['vatNumber']
        if 'paymentTerms' in data:
            supplier.payment_terms = data['paymentTerms']
        if 'rating' in data:
            supplier.rating = int(data['rating'])
        if 'notes' in data:
            supplier.notes = data['notes']
        
        db.session.commit()
        return jsonify(supplier.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@inventory_bp.route('/suppliers/<supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    """Delete a supplier"""
    try:
        supplier = Supplier.query.get_or_404(supplier_id)
        db.session.delete(supplier)
        db.session.commit()
        return jsonify({'message': 'Supplier deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# MATERIALS
# ============================================

@inventory_bp.route('/materials', methods=['GET'])
def get_materials():
    """Get all materials with filters"""
    try:
        category_id = request.args.get('categoryId')
        status = request.args.get('status')
        low_stock = request.args.get('lowStock', 'false').lower() == 'true'
        search = request.args.get('search')
        supplier_id = request.args.get('supplierId')
        
        query = Material.query
        
        if category_id:
            query = query.filter_by(category_id=category_id)
        if status:
            query = query.filter_by(status=status)
        if low_stock:
            query = query.filter(Material.quantity <= Material.reorder_level)
        if supplier_id:
            query = query.filter_by(supplier_id=supplier_id)
        if search:
            query = query.filter(
                db.or_(
                    Material.name.ilike(f'%{search}%'),
                    Material.sku.ilike(f'%{search}%'),
                    Material.description.ilike(f'%{search}%')
                )
            )
        
        materials = query.order_by(Material.name).all()
        return jsonify([m.to_dict() for m in materials])
    except Exception as e:
        print(f"Error in get_materials: {str(e)}")
        return jsonify({'error': str(e)}), 500

@inventory_bp.route('/materials', methods=['POST'])
def create_material():
    """Create a new material"""
    try:
        data = request.json
        
        material = Material(
            id=generate_id(),
            name=data.get('name'),
            category_id=data.get('categoryId'),
            sku=Material.generate_sku(),
            unit=data.get('unit'),
            unit_price=float(data.get('unitPrice', 0)),
            quantity=float(data.get('quantity', 0)),
            min_quantity=float(data.get('minQuantity', 0)),
            max_quantity=float(data.get('maxQuantity', 0)),
            reorder_level=float(data.get('reorderLevel', 0)),
            location=data.get('location'),
            warehouse=data.get('warehouse'),
            supplier_id=data.get('supplierId'),
            description=data.get('description'),
            status=data.get('status', 'active')
        )
        
        db.session.add(material)
        db.session.commit()
        return jsonify(material.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_material: {str(e)}")
        return jsonify({'error': str(e)}), 400

@inventory_bp.route('/materials/<material_id>', methods=['GET'])
def get_material(material_id):
    """Get a specific material"""
    try:
        material = Material.query.get_or_404(material_id)
        data = material.to_dict()
        
        # Get stock movements
        movements = material.stock_movements.order_by(StockMovement.created_at.desc()).limit(50).all()
        data['recentMovements'] = [m.to_dict() for m in movements]
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@inventory_bp.route('/materials/<material_id>', methods=['PUT'])
def update_material(material_id):
    """Update a material"""
    try:
        material = Material.query.get_or_404(material_id)
        data = request.json
        
        if 'name' in data:
            material.name = data['name']
        if 'categoryId' in data:
            material.category_id = data['categoryId']
        if 'unit' in data:
            material.unit = data['unit']
        if 'unitPrice' in data:
            material.unit_price = float(data['unitPrice'])
        if 'quantity' in data:
            material.quantity = float(data['quantity'])
        if 'minQuantity' in data:
            material.min_quantity = float(data['minQuantity'])
        if 'maxQuantity' in data:
            material.max_quantity = float(data['maxQuantity'])
        if 'reorderLevel' in data:
            material.reorder_level = float(data['reorderLevel'])
        if 'location' in data:
            material.location = data['location']
        if 'warehouse' in data:
            material.warehouse = data['warehouse']
        if 'supplierId' in data:
            material.supplier_id = data['supplierId']
        if 'description' in data:
            material.description = data['description']
        if 'status' in data:
            material.status = data['status']
        
        db.session.commit()
        return jsonify(material.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@inventory_bp.route('/materials/<material_id>', methods=['DELETE'])
def delete_material(material_id):
    """Delete a material"""
    try:
        material = Material.query.get_or_404(material_id)
        db.session.delete(material)
        db.session.commit()
        return jsonify({'message': 'Material deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# STOCK MOVEMENTS
# ============================================

@inventory_bp.route('/materials/<material_id>/stock-adjust', methods=['POST'])
def adjust_stock(material_id):
    """Adjust stock quantity for a material"""
    try:
        material = Material.query.get_or_404(material_id)
        data = request.json
        
        quantity_change = float(data.get('quantity', 0))
        movement_type = data.get('movementType', 'adjustment')
        notes = data.get('notes', '')
        created_by = data.get('createdBy', 'System')
        reference_id = data.get('referenceId')
        reference_type = data.get('referenceType')
        
        if quantity_change == 0:
            return jsonify({'error': 'Quantity change cannot be zero'}), 400
        
        # Create stock movement
        movement = material.update_stock(
            quantity_change,
            movement_type,
            reference_id=reference_id,
            reference_type=reference_type,
            notes=notes,
            created_by=created_by
        )
        
        db.session.commit()
        return jsonify({
            'material': material.to_dict(),
            'movement': movement.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error in adjust_stock: {str(e)}")
        return jsonify({'error': str(e)}), 400

@inventory_bp.route('/stock-movements', methods=['GET'])
def get_stock_movements():
    """Get stock movements with filters"""
    try:
        material_id = request.args.get('materialId')
        movement_type = request.args.get('movementType')
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        limit = int(request.args.get('limit', 100))
        
        query = StockMovement.query
        
        if material_id:
            query = query.filter_by(material_id=material_id)
        if movement_type:
            query = query.filter_by(movement_type=movement_type)
        if start_date:
            query = query.filter(StockMovement.created_at >= start_date)
        if end_date:
            query = query.filter(StockMovement.created_at <= end_date)
        
        movements = query.order_by(StockMovement.created_at.desc()).limit(limit).all()
        return jsonify([m.to_dict() for m in movements])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# PURCHASE ORDERS
# ============================================

@inventory_bp.route('/purchase-orders', methods=['GET'])
def get_purchase_orders():
    """Get all purchase orders"""
    try:
        status = request.args.get('status')
        supplier_id = request.args.get('supplierId')
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        
        query = PurchaseOrder.query
        
        if status:
            query = query.filter_by(status=status)
        if supplier_id:
            query = query.filter_by(supplier_id=supplier_id)
        if start_date:
            query = query.filter(PurchaseOrder.order_date >= start_date)
        if end_date:
            query = query.filter(PurchaseOrder.order_date <= end_date)
        
        orders = query.order_by(PurchaseOrder.created_at.desc()).all()
        return jsonify([o.to_dict() for o in orders])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@inventory_bp.route('/purchase-orders', methods=['POST'])
def create_purchase_order():
    """Create a new purchase order"""
    try:
        data = request.json
        
        po = PurchaseOrder(
            id=generate_id(),
            po_number=PurchaseOrder.generate_po_number(),
            supplier_id=data.get('supplierId'),
            order_date=datetime.strptime(data.get('orderDate'), '%Y-%m-%d').date(),
            expected_delivery=datetime.strptime(data.get('expectedDelivery'), '%Y-%m-%d').date() if data.get('expectedDelivery') else None,
            vat_rate=float(data.get('vatRate', 0)),
            status=data.get('status', 'draft'),
            notes=data.get('notes'),
            created_by=data.get('createdBy')
        )
        
        db.session.add(po)
        db.session.commit()
        
        # Add items
        subtotal = 0
        for item_data in data.get('items', []):
            quantity = float(item_data.get('quantity', 0))
            unit_price = float(item_data.get('unitPrice', 0))
            total = quantity * unit_price
            subtotal += total
            
            item = PurchaseOrderItem(
                id=generate_id(),
                po_id=po.id,
                material_id=item_data.get('materialId'),
                quantity=quantity,
                unit_price=unit_price,
                total=total,
                notes=item_data.get('notes')
            )
            db.session.add(item)
        
        po.subtotal = subtotal
        po.vat_amount = subtotal * (po.vat_rate / 100)
        po.total_amount = subtotal + po.vat_amount
        
        db.session.commit()
        return jsonify(po.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_purchase_order: {str(e)}")
        return jsonify({'error': str(e)}), 400

@inventory_bp.route('/purchase-orders/<po_id>', methods=['GET'])
def get_purchase_order(po_id):
    """Get a specific purchase order"""
    try:
        po = PurchaseOrder.query.get_or_404(po_id)
        return jsonify(po.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@inventory_bp.route('/purchase-orders/<po_id>', methods=['PUT'])
def update_purchase_order(po_id):
    """Update a purchase order"""
    try:
        po = PurchaseOrder.query.get_or_404(po_id)
        data = request.json
        
        if 'status' in data:
            po.status = data['status']
        if 'expectedDelivery' in data:
            po.expected_delivery = datetime.strptime(data['expectedDelivery'], '%Y-%m-%d').date()
        if 'notes' in data:
            po.notes = data['notes']
        
        db.session.commit()
        return jsonify(po.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@inventory_bp.route('/purchase-orders/<po_id>/receive', methods=['POST'])
def receive_purchase_order(po_id):
    """Receive items from a purchase order"""
    try:
        po = PurchaseOrder.query.get_or_404(po_id)
        data = request.json
        
        received_by = data.get('receivedBy', 'System')
        
        for item_data in data.get('items', []):
            item = PurchaseOrderItem.query.get(item_data.get('id'))
            if item and item.po_id == po_id:
                received = float(item_data.get('receivedQuantity', 0))
                if received > 0:
                    item.received_quantity += received
                    
                    # Update material stock
                    if item.material_id:
                        material = Material.query.get(item.material_id)
                        if material:
                            material.update_stock(
                                received,
                                'purchase',
                                reference_id=po.id,
                                reference_type='purchase_order',
                                notes=f"Received from PO {po.po_number}",
                                created_by=received_by
                            )
        
        # Check if all items received
        all_received = all(item.received_quantity >= item.quantity for item in po.items.all())
        if all_received:
            po.status = 'received'
            po.actual_delivery = datetime.now().date()
        
        db.session.commit()
        return jsonify(po.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"Error in receive_purchase_order: {str(e)}")
        return jsonify({'error': str(e)}), 400

@inventory_bp.route('/purchase-orders/<po_id>', methods=['DELETE'])
def delete_purchase_order(po_id):
    """Delete a purchase order"""
    try:
        po = PurchaseOrder.query.get_or_404(po_id)
        db.session.delete(po)
        db.session.commit()
        return jsonify({'message': 'Purchase order deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# INVENTORY SUMMARY
# ============================================

@inventory_bp.route('/summary', methods=['GET'])
def get_inventory_summary():
    """Get inventory summary statistics"""
    try:
        total_materials = Material.query.count()
        active_materials = Material.query.filter_by(status='active').count()
        low_stock_items = Material.query.filter(Material.quantity <= Material.reorder_level).count()
        
        total_value = db.session.query(db.func.sum(Material.quantity * Material.unit_price)).scalar() or 0
        
        # Total purchase orders
        total_pos = PurchaseOrder.query.count()
        pending_pos = PurchaseOrder.query.filter(PurchaseOrder.status.in_(['draft', 'sent', 'confirmed'])).count()
        
        # Get low stock items
        low_stock = Material.query.filter(Material.quantity <= Material.reorder_level).limit(10).all()
        
        return jsonify({
            'totalMaterials': total_materials,
            'activeMaterials': active_materials,
            'lowStockItems': low_stock_items,
            'totalStockValue': total_value,
            'totalPurchaseOrders': total_pos,
            'pendingPurchaseOrders': pending_pos,
            'lowStockList': [m.to_dict() for m in low_stock]
        })
    except Exception as e:
        print(f"Error in get_inventory_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500