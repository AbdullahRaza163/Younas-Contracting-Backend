# models/inventory.py
from models import db
from datetime import datetime
import random
import string

class MaterialCategory(db.Model):
    __tablename__ = 'material_categories'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    materials = db.relationship('Material', backref='category', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'materialCount': self.materials.count(),
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    cr_number = db.Column(db.String(50))
    vat_number = db.Column(db.String(50))
    payment_terms = db.Column(db.String(50))
    rating = db.Column(db.Integer, default=3)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    materials = db.relationship('Material', backref='supplier', lazy='dynamic')
    purchase_orders = db.relationship('PurchaseOrder', backref='supplier', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'contactPerson': self.contact_person,
            'email': self.email,
            'phone': self.phone,
            'mobile': self.mobile,
            'address': self.address,
            'city': self.city,
            'country': self.country,
            'crNumber': self.cr_number,
            'vatNumber': self.vat_number,
            'paymentTerms': self.payment_terms,
            'rating': self.rating,
            'notes': self.notes,
            'materialCount': self.materials.count(),
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }


class Material(db.Model):
    __tablename__ = 'materials'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.String(20), db.ForeignKey('material_categories.id', ondelete='SET NULL'))
    sku = db.Column(db.String(50), unique=True)
    unit = db.Column(db.String(20), nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Float, default=0.0)
    min_quantity = db.Column(db.Float, default=0.0)
    max_quantity = db.Column(db.Float, default=0.0)
    reorder_level = db.Column(db.Float, default=0.0)
    location = db.Column(db.String(100))
    warehouse = db.Column(db.String(100))
    supplier_id = db.Column(db.String(20), db.ForeignKey('suppliers.id', ondelete='SET NULL'))
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    stock_movements = db.relationship('StockMovement', backref='material', lazy='dynamic', cascade='all, delete-orphan')
    po_items = db.relationship('PurchaseOrderItem', backref='material', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'categoryId': self.category_id,
            'categoryName': self.category.name if self.category else None,
            'categoryIcon': self.category.icon if self.category else None,
            'sku': self.sku,
            'unit': self.unit,
            'unitPrice': self.unit_price,
            'quantity': self.quantity,
            'minQuantity': self.min_quantity,
            'maxQuantity': self.max_quantity,
            'reorderLevel': self.reorder_level,
            'location': self.location,
            'warehouse': self.warehouse,
            'supplierId': self.supplier_id,
            'supplierName': self.supplier.name if self.supplier else None,
            'description': self.description,
            'status': self.status,
            'needsReorder': self.quantity <= self.reorder_level,
            'stockValue': self.quantity * self.unit_price,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def update_stock(self, quantity_change, movement_type, reference_id=None, reference_type=None, notes=None, created_by=None):
        """Update stock quantity with movement record"""
        previous_quantity = self.quantity
        self.quantity += quantity_change
        
        movement = StockMovement(
            id=''.join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            material_id=self.id,
            movement_type=movement_type,
            quantity=quantity_change,
            previous_quantity=previous_quantity,
            new_quantity=self.quantity,
            reference_id=reference_id,
            reference_type=reference_type,
            unit_price=self.unit_price,
            notes=notes,
            created_by=created_by
        )
        db.session.add(movement)
        return movement
    
    @staticmethod
    def generate_sku():
        prefix = 'MAT'
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"{prefix}-{random_str}"
    
    @staticmethod
    def get_low_stock():
        return Material.query.filter(Material.quantity <= Material.reorder_level).all()


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    
    id = db.Column(db.String(20), primary_key=True)
    po_number = db.Column(db.String(50), unique=True, nullable=False)
    supplier_id = db.Column(db.String(20), db.ForeignKey('suppliers.id', ondelete='SET NULL'))
    order_date = db.Column(db.Date, nullable=False)
    expected_delivery = db.Column(db.Date)
    actual_delivery = db.Column(db.Date)
    status = db.Column(db.String(20), default='draft')
    subtotal = db.Column(db.Float, default=0.0)
    vat_rate = db.Column(db.Float, default=0.0)
    vat_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('PurchaseOrderItem', backref='purchase_order', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        items_list = [i.to_dict() for i in self.items.all()]
        return {
            'id': self.id,
            'poNumber': self.po_number,
            'supplierId': self.supplier_id,
            'supplierName': self.supplier.name if self.supplier else None,
            'orderDate': self.order_date.isoformat() if self.order_date else None,
            'expectedDelivery': self.expected_delivery.isoformat() if self.expected_delivery else None,
            'actualDelivery': self.actual_delivery.isoformat() if self.actual_delivery else None,
            'status': self.status,
            'subtotal': self.subtotal,
            'vatRate': self.vat_rate,
            'vatAmount': self.vat_amount,
            'totalAmount': self.total_amount,
            'notes': self.notes,
            'createdBy': self.created_by,
            'items': items_list,
            'itemCount': len(items_list),
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_totals(self):
        self.subtotal = sum(item.total for item in self.items.all())
        self.vat_amount = self.subtotal * (self.vat_rate / 100)
        self.total_amount = self.subtotal + self.vat_amount
        return self.total_amount
    
    @staticmethod
    def generate_po_number():
        year = datetime.now().year
        count = PurchaseOrder.query.filter(db.extract('year', PurchaseOrder.created_at) == year).count()
        return f"PO-{year}-{str(count + 1).zfill(4)}"


class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'
    
    id = db.Column(db.String(20), primary_key=True)
    po_id = db.Column(db.String(20), db.ForeignKey('purchase_orders.id', ondelete='CASCADE'), nullable=False)
    material_id = db.Column(db.String(20), db.ForeignKey('materials.id', ondelete='SET NULL'))
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    received_quantity = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'poId': self.po_id,
            'materialId': self.material_id,
            'materialName': self.material.name if self.material else None,
            'materialSku': self.material.sku if self.material else None,
            'unit': self.material.unit if self.material else None,
            'quantity': self.quantity,
            'unitPrice': self.unit_price,
            'total': self.total,
            'receivedQuantity': self.received_quantity,
            'remainingQuantity': self.quantity - self.received_quantity,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    
    id = db.Column(db.String(20), primary_key=True)
    material_id = db.Column(db.String(20), db.ForeignKey('materials.id', ondelete='CASCADE'), nullable=False)
    movement_type = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    previous_quantity = db.Column(db.Float, default=0.0)
    new_quantity = db.Column(db.Float, default=0.0)
    reference_id = db.Column(db.String(20))
    reference_type = db.Column(db.String(50))
    unit_price = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'materialId': self.material_id,
            'materialName': self.material.name if self.material else None,
            'movementType': self.movement_type,
            'quantity': self.quantity,
            'previousQuantity': self.previous_quantity,
            'newQuantity': self.new_quantity,
            'referenceId': self.reference_id,
            'referenceType': self.reference_type,
            'unitPrice': self.unit_price,
            'notes': self.notes,
            'createdBy': self.created_by,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }