# routes/expenses.py
from flask import request, jsonify
from datetime import datetime, date as date_cls
from models import Expense, db
from utils.helpers import generate_id
from utils.recurring import generate_due_recurring_expenses
from routes import expenses_bp


def _parse_date(value):
    """Return a date object from 'YYYY-MM-DD' or None."""
    if not value:
        return None
    if isinstance(value, date_cls):
        return value
    return datetime.strptime(value, '%Y-%m-%d').date()


# ======================================================================
# GET /api/expenses
# ======================================================================
@expenses_bp.route('', methods=['GET'])
def get_expenses():
    """Get all expenses with optional filters"""
    try:
        # Make sure any due recurring expenses exist before we return.
        try:
            generate_due_recurring_expenses()
        except Exception as inner:
            print(f"[recurring] generation on GET failed: {inner}")

        site_id = request.args.get('siteId')
        category = request.args.get('category')
        month = request.args.get('month')
        status = request.args.get('status')
        include_generated = request.args.get('includeGenerated', 'true').lower() != 'false'

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

        rows = []
        for e in expenses:
            # Hide generated children only if explicitly requested
            if not include_generated and e.parent_expense_id:
                continue
            rows.append(e.to_dict())

        return jsonify(rows)
    except Exception as e:
        print(f"Error in get_expenses: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ======================================================================
# POST /api/expenses — create
# ======================================================================
@expenses_bp.route('', methods=['POST'])
def create_expense():
    """Create a new expense (may be a recurring rule)"""
    try:
        data = request.json
        expense_date = datetime.strptime(data.get('date'), '%Y-%m-%d').date()

        is_recurring = bool(data.get('isRecurring', False))
        recurrence_type = data.get('recurrenceType') if is_recurring else None
        recurrence_start = _parse_date(data.get('recurrenceStart')) if is_recurring else None
        recurrence_end = _parse_date(data.get('recurrenceEnd')) if is_recurring else None

        if is_recurring and recurrence_start is None:
            recurrence_start = expense_date

        expense = Expense(
            id=generate_id(),
            date=expense_date,
            site_id=data.get('siteId'),
            category=data.get('category'),
            description=data.get('description', ''),
            amount=float(data.get('amount', 0)),
            quantity=float(data.get('quantity', 1)),
            unit=data.get('unit', ''),
            is_recurring=is_recurring,
            recurrence_type=recurrence_type,
            recurrence_start=recurrence_start,
            recurrence_end=recurrence_end,
            receipt_url=data.get('receiptUrl', ''),
            note=data.get('note', ''),
            month=expense_date.strftime('%Y-%m'),
            expense_type=data.get('expenseType', 'project'),
            status=data.get('status', 'draft'),
            vendor=data.get('vendor', ''),
            invoice_number=data.get('invoiceNumber', ''),
            payment_method=data.get('paymentMethod', ''),
            created_by=data.get('createdBy', 'system'),
            cost_center=data.get('costCenter', ''),
        )
        db.session.add(expense)
        db.session.commit()

        # Fire generation immediately so children land for today if due
        try:
            created = generate_due_recurring_expenses()
            if created:
                print(f"[recurring] post-create generated {created} rows")
        except Exception as inner:
            print(f"[recurring] post-create generation failed: {inner}")

        return jsonify(expense.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_expense: {str(e)}")
        return jsonify({'error': str(e)}), 400


# ======================================================================
# GET /api/expenses/<id>
# ======================================================================
@expenses_bp.route('/<expense_id>', methods=['GET'])
def get_expense(expense_id):
    """Get a specific expense"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        return jsonify(expense.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404


# ======================================================================
# PUT /api/expenses/<id>
# ======================================================================
@expenses_bp.route('/<expense_id>', methods=['PUT'])
def update_expense(expense_id):
    """Update an expense"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        data = request.json

        if 'date' in data and data['date']:
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

        # Recurring fields
        if 'isRecurring' in data:
            expense.is_recurring = bool(data['isRecurring'])
        if 'recurrenceType' in data:
            expense.recurrence_type = data['recurrenceType']
        if 'recurrenceStart' in data:
            expense.recurrence_start = _parse_date(data['recurrenceStart'])
        if 'recurrenceEnd' in data:
            expense.recurrence_end = _parse_date(data['recurrenceEnd'])

        # If it stopped being recurring, clear stale rule metadata
        if not expense.is_recurring:
            expense.recurrence_type = None
            expense.recurrence_start = None
            expense.recurrence_end = None
            expense.last_generated = None

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

        # Regenerate so rule changes take effect immediately
        try:
            generate_due_recurring_expenses()
        except Exception as inner:
            print(f"[recurring] post-update generation failed: {inner}")

        return jsonify(expense.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ======================================================================
# DELETE /api/expenses/<id>
# ======================================================================
@expenses_bp.route('/<expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    """Delete an expense (cascades to its generated children)"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        db.session.delete(expense)
        db.session.commit()
        return jsonify({'message': 'Expense deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ======================================================================
# PUT /api/expenses/<id>/approve
# ======================================================================
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


# ======================================================================
# PUT /api/expenses/<id>/paid
# ======================================================================
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


# ======================================================================
# GET /api/expenses/categories
# ======================================================================
@expenses_bp.route('/categories', methods=['GET'])
def get_expense_categories():
    """Get all expense categories"""
    try:
        categories = [
            {'id': 'electricity', 'label': 'Electricity Bill'},
            {'id': 'lmra',        'label': 'LMRA Fees'},
            {'id': 'gossi',       'label': 'Gossi Fees'},
            {'id': 'car_patrol',  'label': 'Car Patrol'},
            {'id': 'office_rent', 'label': 'Office Rent'},
            {'id': 'water',       'label': 'Water Bill'},
            {'id': 'internet',    'label': 'Internet Bill'},
            {'id': 'material',    'label': 'Material'},
            {'id': 'equipment',   'label': 'Equipment'},
            {'id': 'transport',   'label': 'Transport'},
            {'id': 'labour',      'label': 'Labour'},
            {'id': 'maintenance', 'label': 'Maintenance'},
            {'id': 'insurance',   'label': 'Insurance'},
            {'id': 'tax',         'label': 'Tax'},
            {'id': 'overhead',    'label': 'Overhead'},
            {'id': 'other',       'label': 'Other'},
        ]
        return jsonify(categories)
    except Exception as e:
        print(f"Error in get_expense_categories: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ======================================================================
# GET /api/expenses/recurring — list all active recurring rules
# ======================================================================
@expenses_bp.route('/recurring', methods=['GET'])
def list_recurring_rules():
    """List all recurring rules (top-level rows only) with next-due date."""
    try:
        rules = Expense.query.filter(
            Expense.is_recurring.is_(True),
            Expense.parent_expense_id.is_(None),
        ).order_by(Expense.date.desc()).all()

        from utils.recurring import _next_date  # reuse the calculator

        out = []
        for r in rules:
            anchor = r.recurrence_start or r.date
            cursor = r.last_generated or anchor
            nxt = _next_date(cursor, r.recurrence_type, anchor)
            d = r.to_dict()
            d['nextDueDate'] = nxt.isoformat() if nxt else None
            out.append(d)

        return jsonify(out)
    except Exception as e:
        print(f"Error in list_recurring_rules: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ======================================================================
# POST /api/expenses/recurring/generate — force generation now
# ======================================================================
@expenses_bp.route('/recurring/generate', methods=['POST'])
def force_generate_recurring():
    """Manually trigger generation of due recurring expenses."""
    try:
        created = generate_due_recurring_expenses()
        return jsonify({'created': created, 'message': f'{created} rows generated'})
    except Exception as e:
        db.session.rollback()
        print(f"Error in force_generate_recurring: {str(e)}")
        return jsonify({'error': str(e)}), 500