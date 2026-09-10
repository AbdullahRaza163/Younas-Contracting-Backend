from models import db
from datetime import datetime

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.String(20), primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='SET NULL'))
    client_name = db.Column(db.String(200), nullable=False)
    client_address = db.Column(db.Text)
    client_crn = db.Column(db.String(50))
    invoice_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date)
    subtotal = db.Column(db.Float, default=0.0)
    vat_rate = db.Column(db.Float, default=0.0)
    vat_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    amount_in_words = db.Column(db.String(500))
    invoice_type = db.Column(db.String(20), default='simple')  # simple, detailed
    status = db.Column(db.String(20), default='draft')  # draft, sent, paid, overdue, cancelled
    items = db.Column(db.JSON, default=[])
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'invoiceNumber': self.invoice_number,
            'siteId': self.site_id,
            'clientName': self.client_name,
            'clientAddress': self.client_address,
            'clientCrn': self.client_crn,
            'invoiceDate': self.invoice_date.isoformat() if self.invoice_date else None,
            'dueDate': self.due_date.isoformat() if self.due_date else None,
            'subtotal': self.subtotal,
            'vatRate': self.vat_rate,
            'vatAmount': self.vat_amount,
            'totalAmount': self.total_amount,
            'amountInWords': self.amount_in_words,
            'invoiceType': self.invoice_type,
            'status': self.status,
            'items': self.items,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_totals(self):
        """Calculate subtotal, VAT, and total"""
        self.subtotal = sum(item.get('amount', 0) for item in self.items)
        self.vat_amount = self.subtotal * (self.vat_rate / 100)
        self.total_amount = self.subtotal + self.vat_amount
        return self.total_amount
    
    def add_item(self, description, quantity, unit_price, amount=None):
        """Add an item to the invoice"""
        if amount is None:
            amount = quantity * unit_price
        
        item = {
            'description': description,
            'quantity': quantity,
            'unitPrice': unit_price,
            'amount': amount
        }
        self.items.append(item)
        self.calculate_totals()
        return item
    
    def remove_item(self, index):
        """Remove an item from the invoice"""
        if 0 <= index < len(self.items):
            self.items.pop(index)
            self.calculate_totals()
            return True
        return False
    
    def mark_sent(self):
        """Mark invoice as sent"""
        self.status = 'sent'
    
    def mark_paid(self):
        """Mark invoice as paid"""
        self.status = 'paid'
    
    def mark_overdue(self):
        """Mark invoice as overdue"""
        self.status = 'overdue'
    
    @staticmethod
    def get_invoices_by_site(site_id):
        return Invoice.query.filter_by(site_id=site_id).order_by(Invoice.invoice_date.desc()).all()
    
    @staticmethod
    def get_invoices_by_status(status):
        return Invoice.query.filter_by(status=status).order_by(Invoice.invoice_date.desc()).all()