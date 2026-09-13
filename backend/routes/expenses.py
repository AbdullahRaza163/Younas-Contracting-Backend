from flask import request, jsonify
from datetime import datetime
from models import Expense, db
from utils.helpers import generate_id
from routes import expenses_bp

@expenses_bp.route('', methods=['GET'])
def get_expenses():
    """Get all expenses with optional filters"""
    try:
        site_id = request.args.get('siteId')
        category = request.args.get('category')
        month = request.args.get('month')
        status = request.args.get('status')
        
        query = Expense.query
        if site_id:
            query = query.filter_by(site_id=site_id)
        if category:
            query = query.filter_by(category=category)
        if month:
            query = query.filter_by(month=month)
        if status:
            query = query.filter_by(status=status)
        
        expenses = query.order_by(Expense.date.desc()).all()
        return jsonify([e.to_dict() for e in expenses])
    except Exception as e:
        print(f"Error in get_expenses: {str(e)}")
        return jsonify({'error': str(e)}), 500

@expenses_bp.route('', methods=['POST'])
def create_expense():
    """Create a new expense"""
    try:
        data = request.json
        expense_date = datetime.strptime(data.get('date'), '%Y-%m-%d').date()
        
        expense = Expense(
            id=generate_id(),
            date=expense_date,
            site_id=data.get('siteId'),
            category=data.get('category'),
            description=data.get('description', ''),
            amount=float(data.get('amount', 0)),
            quantity=float(data.get('quantity', 1)),
            unit=data.get('unit', ''),
            is_recurring=data.get('isRecurring', False),
            recurrence_type=data.get('recurrenceType'),
            receipt_url=data.get('receiptUrl', ''),
            note=data.get('note', ''),
            month=expense_date.strftime('%Y-%m'),
            expense_type=data.get('expenseType', 'project'),
            status=data.get('status', 'draft'),
            vendor=data.get('vendor', ''),
            invoice_number=data.get('invoiceNumber', ''),
            payment_method=data.get('paymentMethod', ''),
            created_by=data.get('createdBy', 'system'),
            cost_center=data.get('costCenter', '')
        )
        db.session.add(expense)
        db.session.commit()
        return jsonify(expense.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_expense: {str(e)}")
        return jsonify({'error': str(e)}), 400

@expenses_bp.route('/<expense_id>', methods=['GET'])
def get_expense(expense_id):
    """Get a specific expense"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        return jsonify(expense.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@expenses_bp.route('/<expense_id>', methods=['PUT'])
def update_expense(expense_id):
    """Update an expense"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        data = request.json
        
        if 'date' in data:
            expense.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            expense.month = expense.date.strftime('%Y-%m')
        if 'siteId' in data:
            expense.site_id = data['siteId']
        if 'category' in data:
            expense.category = data['category']
        if 'description' in data:
            expense.description = data['description']
        if 'amount' in data:
            expense.amount = float(data['amount'])
        if 'quantity' in data:
            expense.quantity = float(data['quantity'])
        if 'unit' in data:
            expense.unit = data['unit']
        if 'isRecurring' in data:
            expense.is_recurring = data['isRecurring']
        if 'recurrenceType' in data:
            expense.recurrence_type = data['recurrenceType']
        if 'receiptUrl' in data:
            expense.receipt_url = data['receiptUrl']
        if 'note' in data:
            expense.note = data['note']
        if 'status' in data:
            expense.status = data['status']
        if 'vendor' in data:
            expense.vendor = data['vendor']
        if 'invoiceNumber' in data:
            expense.invoice_number = data['invoiceNumber']
        if 'paymentMethod' in data:
            expense.payment_method = data['paymentMethod']
        if 'costCenter' in data:
            expense.cost_center = data['costCenter']
        
        db.session.commit()
        return jsonify(expense.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@expenses_bp.route('/<expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    """Delete an expense"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        db.session.delete(expense)
        db.session.commit()
        return jsonify({'message': 'Expense deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@expenses_bp.route('/<expense_id>/approve', methods=['PUT'])
def approve_expense(expense_id):
    """Approve an expense"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        data = request.json
        expense.approve(data.get('approvedBy', 'system'))
        db.session.commit()
        return jsonify(expense.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@expenses_bp.route('/<expense_id>/paid', methods=['PUT'])
def mark_expense_paid(expense_id):
    """Mark expense as paid"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        expense.mark_paid()
        db.session.commit()
        return jsonify(expense.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@expenses_bp.route('/categories', methods=['GET'])
def get_expense_categories():
    """Get all expense categories"""
    try:
        categories = [
            {'id': 'electricity', 'label': 'Electricity Bill'},
            {'id': 'lmra', 'label': 'LMRA Fees'},
            {'id': 'gossi', 'label': 'Gossi Fees'},
            {'id': 'car_patrol', 'label': 'Car Patrol'},
            {'id': 'office_rent', 'label': 'Office Rent'},
            {'id': 'water', 'label': 'Water Bill'},
            {'id': 'internet', 'label': 'Internet Bill'},
            {'id': 'material', 'label': 'Material'},
            {'id': 'equipment', 'label': 'Equipment'},
            {'id': 'transport', 'label': 'Transport'},
            {'id': 'labour', 'label': 'Labour'},
            {'id': 'maintenance', 'label': 'Maintenance'},
            {'id': 'insurance', 'label': 'Insurance'},
            {'id': 'tax', 'label': 'Tax'},
            {'id': 'overhead', 'label': 'Overhead'},
            {'id': 'other', 'label': 'Other'}
        ]
        return jsonify(categories)
    except Exception as e:
        print(f"Error in get_expense_categories: {str(e)}")
        return jsonify({'error': str(e)}), 500