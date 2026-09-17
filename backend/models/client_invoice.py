# models/client_invoice.py
from datetime import datetime, timezone
from models import db


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ClientInvoice(db.Model):
    """
    ⭐ ISOLATED table for client invoicing.

    NO foreign keys into projects / entries / expenses / invoices / sites / workers.
    Nothing in this table appears in dashboard, finance, or any other screen.
    Everything (client name, site name, items) is stored as free-form text/JSON.
    """
    __tablename__ = 'client_invoices'

    id = db.Column(db.String(50), primary_key=True)
    invoice_number = db.Column(db.String(50), nullable=False, unique=True, index=True)

    # ---------- Client info (free-form, no FK) ----------
    client_name = db.Column(db.String(255), nullable=False, index=True)
    client_address = db.Column(db.Text, default='')
    client_crn = db.Column(db.String(100), default='')       # Commercial Registration #
    contact_person = db.Column(db.String(255), default='')
    cpr = db.Column(db.String(100), default='')

    # ---------- Optional site name (free-form, no FK) ----------
    site_name = db.Column(db.String(255), default='')

    # ---------- Dates ----------
    invoice_date = db.Column(db.Date, nullable=False, index=True)
    due_date = db.Column(db.Date)

    # ---------- Amounts ----------
    subtotal = db.Column(db.Float, default=0.0)
    vat_rate = db.Column(db.Float, default=0.0)
    vat_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0, index=True)
    amount_in_words = db.Column(db.Text, default='')

    # ---------- Meta ----------
    invoice_type = db.Column(db.String(20), default='simple')      # simple | vat
    status = db.Column(db.String(20), default='draft', index=True)  # draft | sent | paid | overdue
    subject = db.Column(db.Text, default='')
    notes = db.Column(db.Text, default='')

    # ---------- Items stored as JSON ----------
    items_json = db.Column(db.Text, default='[]')

    # ---------- Timestamps ----------
    created_at = db.Column(db.DateTime, default=_utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    # ------------------------------------------------------------
    def to_dict(self):
        import json as _json
        try:
            items = _json.loads(self.items_json) if self.items_json else []
        except Exception:
            items = []

        return {
            'id': self.id,
            'invoiceNumber': self.invoice_number,
            'clientName': self.client_name,
            'clientAddress': self.client_address or '',
            'clientCrn': self.client_crn or '',
            'contactPerson': self.contact_person or '',
            'cpr': self.cpr or '',
            'siteName': self.site_name or '',
            'invoiceDate': self.invoice_date.isoformat() if self.invoice_date else None,
            'dueDate': self.due_date.isoformat() if self.due_date else None,
            'subtotal': float(self.subtotal or 0),
            'vatRate': float(self.vat_rate or 0),
            'vatAmount': float(self.vat_amount or 0),
            'totalAmount': float(self.total_amount or 0),
            'amountInWords': self.amount_in_words or '',
            'invoiceType': self.invoice_type or 'simple',
            'status': self.status or 'draft',
            'subject': self.subject or '',
            'notes': self.notes or '',
            'items': items,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<ClientInvoice {self.invoice_number} · {self.client_name}>'