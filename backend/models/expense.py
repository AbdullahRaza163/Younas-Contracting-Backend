from models import db
from datetime import datetime

class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.String(20), primary_key=True)
    date = db.Column(db.Date, nullable=False)
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='CASCADE'))
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    amount = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, default=1.0)
    unit = db.Column(db.String(20))
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_type = db.Column(db.String(20))  # daily, weekly, monthly, yearly
    receipt_url = db.Column(db.Text)
    note = db.Column(db.Text)
    month = db.Column(db.String(7))
    expense_type = db.Column(db.String(20), default='project')  # project, overhead, general
    status = db.Column(db.String(20), default='draft')  # draft, approved, paid, cancelled
    vendor = db.Column(db.String(200))
    invoice_number = db.Column(db.String(50))
    payment_method = db.Column(db.String(50))
    approved_by = db.Column(db.String(50))
    approval_date = db.Column(db.Date)
    created_by = db.Column(db.String(50))
    cost_center = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'siteId': self.site_id,
            'siteName': self.site.name if self.site else None,
            'category': self.category,
            'description': self.description,
            'amount': self.amount,
            'quantity': self.quantity,
            'unit': self.unit,
            'isRecurring': self.is_recurring,
            'recurrenceType': self.recurrence_type,
            'receiptUrl': self.receipt_url,
            'note': self.note,
            'month': self.month,
            'expenseType': self.expense_type,
            'status': self.status,
            'vendor': self.vendor,
            'invoiceNumber': self.invoice_number,
            'paymentMethod': self.payment_method,
            'approvedBy': self.approved_by,
            'approvalDate': self.approval_date.isoformat() if self.approval_date else None,
            'createdBy': self.created_by,
            'costCenter': self.cost_center,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def approve(self, approved_by):
        """Approve the expense"""
        self.status = 'approved'
        self.approved_by = approved_by
        self.approval_date = datetime.now().date()
    
    def mark_paid(self):
        """Mark expense as paid"""
        self.status = 'paid'
    
    def cancel(self):
        """Cancel the expense"""
        self.status = 'cancelled'
    
    @staticmethod
    def get_expenses_by_site(site_id):
        return Expense.query.filter_by(site_id=site_id).order_by(Expense.date.desc()).all()
    
    @staticmethod
    def get_expenses_by_month(month, site_id=None):
        query = Expense.query.filter_by(month=month)
        if site_id:
            query = query.filter_by(site_id=site_id)
        return query.order_by(Expense.date.desc()).all()
    
    @staticmethod
    def get_expenses_by_category(category, site_id=None):
        query = Expense.query.filter_by(category=category)
        if site_id:
            query = query.filter_by(site_id=site_id)
        return query.order_by(Expense.date.desc()).all()