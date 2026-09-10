from models import db
from datetime import datetime

class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text)
    sku = db.Column(db.String(50))
    tax_rate = db.Column(db.Float, default=0.0)
    is_taxable = db.Column(db.Boolean, default=False)
    quantity = db.Column(db.Float, default=0.0)
    reorder_level = db.Column(db.Float, default=0.0)
    supplier = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'unit': self.unit,
            'unitPrice': self.unit_price,
            'description': self.description,
            'sku': self.sku,
            'taxRate': self.tax_rate,
            'isTaxable': self.is_taxable,
            'quantity': self.quantity,
            'reorderLevel': self.reorder_level,
            'supplier': self.supplier,
            'isActive': self.is_active,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def update_stock(self, quantity_change):
        """Update item quantity"""
        self.quantity += quantity_change
        return self.quantity
    
    def is_low_stock(self):
        """Check if item is below reorder level"""
        return self.quantity <= self.reorder_level
    
    @staticmethod
    def get_items_by_category(category):
        return Item.query.filter_by(category=category, is_active=True).all()
    
    @staticmethod
    def get_low_stock_items():
        return Item.query.filter(Item.quantity <= Item.reorder_level, Item.is_active == True).all()