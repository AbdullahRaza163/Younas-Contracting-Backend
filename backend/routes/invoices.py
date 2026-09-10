from flask import request, jsonify
from datetime import datetime
from models import Invoice, db
from utils.helpers import generate_id, generate_invoice_number
from routes import invoices_bp

@invoices_bp.route('', methods=['GET'])
def get_invoices():
    """Get all invoices with optional filters"""
    try:
        status = request.args.get('status')
        site_id = request.args.get('siteId')
        
        query = Invoice.query
        if status:
            query = query.filter_by(status=status)
        if site_id:
            query = query.filter_by(site_id=site_id)
        
        invoices = query.order_by(Invoice.invoice_date.desc()).all()
        return jsonify([i.to_dict() for i in invoices])
    except Exception as e:
        print(f"Error in get_invoices: {str(e)}")
        return jsonify({'error': str(e)}), 500

@invoices_bp.route('/generate-number', methods=['GET'])
def generate_invoice_number_route():
    """Generate a new invoice number"""
    try:
        number = generate_invoice_number()
        return jsonify({'invoiceNumber': number})
    except Exception as e:
        print(f"Error generating invoice number: {str(e)}")
        return jsonify({'error': str(e)}), 500

@invoices_bp.route('', methods=['POST'])
def create_invoice():
    """Create a new invoice"""
    try:
        data = request.json
        
        invoice = Invoice(
            id=generate_id(),
            invoice_number=data.get('invoiceNumber') or generate_invoice_number(),
            site_id=data.get('siteId'),
            client_name=data.get('clientName'),
            client_address=data.get('clientAddress', ''),
            client_crn=data.get('clientCrn', ''),
            invoice_date=datetime.strptime(data.get('invoiceDate'), '%Y-%m-%d').date(),
            due_date=datetime.strptime(data.get('dueDate'), '%Y-%m-%d').date() if data.get('dueDate') else None,
            subtotal=float(data.get('subtotal', 0)),
            vat_rate=float(data.get('vatRate', 0)),
            vat_amount=float(data.get('vatAmount', 0)),
            total_amount=float(data.get('totalAmount', 0)),
            amount_in_words=data.get('amountInWords', ''),
            invoice_type=data.get('invoiceType', 'simple'),
            status=data.get('status', 'draft'),
            items=data.get('items', []),
            notes=data.get('notes', '')
        )
        db.session.add(invoice)
        db.session.commit()
        return jsonify(invoice.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_invoice: {str(e)}")
        return jsonify({'error': str(e)}), 400

@invoices_bp.route('/<invoice_id>', methods=['GET'])
def get_invoice(invoice_id):
    """Get a specific invoice"""
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        return jsonify(invoice.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@invoices_bp.route('/<invoice_id>', methods=['PUT'])
def update_invoice(invoice_id):
    """Update an invoice"""
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        data = request.json
        
        if 'clientName' in data:
            invoice.client_name = data['clientName']
        if 'clientAddress' in data:
            invoice.client_address = data['clientAddress']
        if 'clientCrn' in data:
            invoice.client_crn = data['clientCrn']
        if 'invoiceDate' in data:
            invoice.invoice_date = datetime.strptime(data['invoiceDate'], '%Y-%m-%d').date()
        if 'dueDate' in data and data['dueDate']:
            invoice.due_date = datetime.strptime(data['dueDate'], '%Y-%m-%d').date()
        if 'subtotal' in data:
            invoice.subtotal = float(data['subtotal'])
        if 'vatRate' in data:
            invoice.vat_rate = float(data['vatRate'])
        if 'vatAmount' in data:
            invoice.vat_amount = float(data['vatAmount'])
        if 'totalAmount' in data:
            invoice.total_amount = float(data['totalAmount'])
        if 'amountInWords' in data:
            invoice.amount_in_words = data['amountInWords']
        if 'invoiceType' in data:
            invoice.invoice_type = data['invoiceType']
        if 'status' in data:
            invoice.status = data['status']
        if 'items' in data:
            invoice.items = data['items']
        if 'notes' in data:
            invoice.notes = data['notes']
        
        db.session.commit()
        return jsonify(invoice.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@invoices_bp.route('/<invoice_id>', methods=['DELETE'])
def delete_invoice(invoice_id):
    """Delete an invoice"""
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        db.session.delete(invoice)
        db.session.commit()
        return jsonify({'message': 'Invoice deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@invoices_bp.route('/<invoice_id>/send', methods=['PUT'])
def send_invoice(invoice_id):
    """Mark invoice as sent"""
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        invoice.mark_sent()
        db.session.commit()
        return jsonify(invoice.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@invoices_bp.route('/<invoice_id>/pay', methods=['PUT'])
def mark_invoice_paid(invoice_id):
    """Mark invoice as paid"""
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        invoice.mark_paid()
        db.session.commit()
        return jsonify(invoice.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400