# routes/client_invoices.py
import json
from datetime import datetime
from flask import request, jsonify
from models import db, ClientInvoice
from utils.helpers import generate_id
from routes import client_invoices_bp


# ============================================
# HELPERS
# ============================================
def _parse_date(s):
    """Accept 'YYYY-MM-DD' or full ISO; return date or None."""
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], '%Y-%m-%d').date()
    except Exception:
        return None


def _next_invoice_number():
    """
    Generates CINV-YYYY-0001, CINV-YYYY-0002, ...
    Scoped ONLY to the client_invoices table.
    Prefix 'CINV-' distinguishes from daily 'INV-' invoices.
    """
    year = datetime.utcnow().year
    prefix = f'CINV-{year}-'
    last = ClientInvoice.query.filter(
        ClientInvoice.invoice_number.like(f'{prefix}%')
    ).order_by(ClientInvoice.invoice_number.desc()).first()

    seq = 1
    if last:
        try:
            seq = int(last.invoice_number.split('-')[-1]) + 1
        except Exception:
            seq = 1
    return f'{prefix}{seq:04d}'


# ============================================
# GET /api/client-invoices   — list w/ filters
# ============================================
@client_invoices_bp.route('', methods=['GET'])
def list_client_invoices():
    try:
        q = ClientInvoice.query

        status = request.args.get('status')
        search = request.args.get('search')
        date_from = request.args.get('dateFrom')
        date_to = request.args.get('dateTo')

        if status and status != 'all':
            q = q.filter(ClientInvoice.status == status)
        if search:
            like = f'%{search}%'
            q = q.filter(db.or_(
                ClientInvoice.invoice_number.ilike(like),
                ClientInvoice.client_name.ilike(like),
            ))
        if date_from:
            d = _parse_date(date_from)
            if d:
                q = q.filter(ClientInvoice.invoice_date >= d)
        if date_to:
            d = _parse_date(date_to)
            if d:
                q = q.filter(ClientInvoice.invoice_date <= d)

        rows = q.order_by(
            ClientInvoice.invoice_date.desc(),
            ClientInvoice.created_at.desc()
        ).all()

        return jsonify([r.to_dict() for r in rows])
    except Exception as e:
        print(f'Error in list_client_invoices: {e}')
        return jsonify({'error': str(e)}), 500


# ============================================
# GET /api/client-invoices/next-number
# ============================================
@client_invoices_bp.route('/next-number', methods=['GET'])
def next_client_invoice_number():
    try:
        return jsonify({'invoiceNumber': _next_invoice_number()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# GET /api/client-invoices/<id>
# ============================================
@client_invoices_bp.route('/<invoice_id>', methods=['GET'])
def get_client_invoice(invoice_id):
    rec = ClientInvoice.query.get(invoice_id)
    if not rec:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(rec.to_dict())


# ============================================
# POST /api/client-invoices   — create
# ============================================
@client_invoices_bp.route('', methods=['POST'])
def create_client_invoice():
    try:
        data = request.json or {}

        invoice_number = data.get('invoiceNumber') or _next_invoice_number()
        items = data.get('items') or []

        subtotal = sum(float(i.get('total') or 0) for i in items)
        vat_rate = float(data.get('vatRate') or 0)
        vat_amount = subtotal * (vat_rate / 100) if data.get('invoiceType') == 'vat' else 0.0
        total = subtotal + vat_amount

        rec = ClientInvoice(
            id=generate_id(),
            invoice_number=invoice_number,
            client_name=(data.get('clientName') or '').strip(),
            client_address=data.get('clientAddress', ''),
            client_crn=data.get('clientCrn', ''),
            contact_person=data.get('contactPerson', ''),
            cpr=data.get('cpr', ''),
            site_name=data.get('siteName', ''),
            invoice_date=_parse_date(data.get('invoiceDate')) or datetime.utcnow().date(),
            due_date=_parse_date(data.get('dueDate')),
            subtotal=subtotal,
            vat_rate=vat_rate,
            vat_amount=vat_amount,
            total_amount=total,
            amount_in_words=data.get('amountInWords', ''),
            invoice_type=data.get('invoiceType', 'simple'),
            status=data.get('status', 'draft'),
            subject=data.get('subject', ''),
            notes=data.get('notes', ''),
            items_json=json.dumps(items),
        )

        db.session.add(rec)
        db.session.commit()
        return jsonify(rec.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f'Error in create_client_invoice: {e}')
        return jsonify({'error': str(e)}), 400


# ============================================
# PUT /api/client-invoices/<id>   — update
# ============================================
@client_invoices_bp.route('/<invoice_id>', methods=['PUT'])
def update_client_invoice(invoice_id):
    try:
        rec = ClientInvoice.query.get(invoice_id)
        if not rec:
            return jsonify({'error': 'Not found'}), 404

        data = request.json or {}

        # Simple fields
        if 'clientName' in data:      rec.client_name = data['clientName'] or ''
        if 'clientAddress' in data:   rec.client_address = data['clientAddress'] or ''
        if 'clientCrn' in data:       rec.client_crn = data['clientCrn'] or ''
        if 'contactPerson' in data:   rec.contact_person = data['contactPerson'] or ''
        if 'cpr' in data:             rec.cpr = data['cpr'] or ''
        if 'siteName' in data:        rec.site_name = data['siteName'] or ''
        if 'subject' in data:         rec.subject = data['subject'] or ''
        if 'notes' in data:           rec.notes = data['notes'] or ''
        if 'status' in data:          rec.status = data['status']
        if 'invoiceType' in data:     rec.invoice_type = data['invoiceType']

        if 'invoiceNumber' in data and data['invoiceNumber']:
            rec.invoice_number = data['invoiceNumber']

        # Dates
        if 'invoiceDate' in data:
            d = _parse_date(data['invoiceDate'])
            if d:
                rec.invoice_date = d
        if 'dueDate' in data:
            rec.due_date = _parse_date(data['dueDate'])

        # Items + recompute totals
        items = data.get('items', None)
        if items is not None:
            rec.items_json = json.dumps(items)
            subtotal = sum(float(i.get('total') or 0) for i in items)
        else:
            try:
                existing_items = json.loads(rec.items_json or '[]')
            except Exception:
                existing_items = []
            subtotal = sum(float(i.get('total') or 0) for i in existing_items)

        if 'vatRate' in data:
            rec.vat_rate = float(data['vatRate'] or 0)

        vat_amount = subtotal * (rec.vat_rate / 100) if rec.invoice_type == 'vat' else 0.0
        rec.subtotal = subtotal
        rec.vat_amount = vat_amount
        rec.total_amount = subtotal + vat_amount

        if 'amountInWords' in data:
            rec.amount_in_words = data['amountInWords']

        db.session.commit()
        return jsonify(rec.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f'Error in update_client_invoice: {e}')
        return jsonify({'error': str(e)}), 400


# ============================================
# DELETE /api/client-invoices/<id>
# ============================================
@client_invoices_bp.route('/<invoice_id>', methods=['DELETE'])
def delete_client_invoice(invoice_id):
    try:
        rec = ClientInvoice.query.get(invoice_id)
        if not rec:
            return jsonify({'error': 'Not found'}), 404
        db.session.delete(rec)
        db.session.commit()
        return jsonify({'message': 'Deleted'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400