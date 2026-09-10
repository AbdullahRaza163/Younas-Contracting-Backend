# routes/advances.py
from flask import request, jsonify
from models import db
from models.worker import Worker
from models.advance import (
    AdvanceType, 
    EmployeeAdvance, 
    AdvanceRepayment, 
    AdvanceSalaryDeduction
)
from utils.helpers import generate_id
from datetime import datetime, timedelta
from routes import advances_bp  # ← IMPORT THE EXISTING BLUEPRINT

# ============================================
# ADVANCE TYPES
# ============================================

@advances_bp.route('/types', methods=['GET'])
def get_advance_types():
    """Get all advance types"""
    try:
        types = AdvanceType.query.filter_by(is_active=True).all()
        return jsonify([t.to_dict() for t in types])
    except Exception as e:
        print(f"Error in get_advance_types: {str(e)}")
        return jsonify({'error': str(e)}), 500

@advances_bp.route('/types', methods=['POST'])
def create_advance_type():
    """Create a new advance type"""
    try:
        data = request.json
        advance_type = AdvanceType(
            id=generate_id(),
            name=data.get('name'),
            description=data.get('description'),
            max_amount=float(data.get('maxAmount', 0)),
            default_tenure=int(data.get('defaultTenure', 1))
        )
        db.session.add(advance_type)
        db.session.commit()
        return jsonify(advance_type.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@advances_bp.route('/types/<type_id>', methods=['PUT'])
def update_advance_type(type_id):
    """Update an advance type"""
    try:
        advance_type = AdvanceType.query.get_or_404(type_id)
        data = request.json
        
        if 'name' in data:
            advance_type.name = data['name']
        if 'description' in data:
            advance_type.description = data['description']
        if 'maxAmount' in data:
            advance_type.max_amount = float(data['maxAmount'])
        if 'defaultTenure' in data:
            advance_type.default_tenure = int(data['defaultTenure'])
        if 'isActive' in data:
            advance_type.is_active = data['isActive']
        
        db.session.commit()
        return jsonify(advance_type.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@advances_bp.route('/types/<type_id>', methods=['DELETE'])
def delete_advance_type(type_id):
    """Delete an advance type"""
    try:
        advance_type = AdvanceType.query.get_or_404(type_id)
        db.session.delete(advance_type)
        db.session.commit()
        return jsonify({'message': 'Advance type deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ============================================
# EMPLOYEE ADVANCES
# ============================================

@advances_bp.route('', methods=['GET'])
def get_advances():
    """Get all advances with filters"""
    try:
        employee_id = request.args.get('employeeId')
        status = request.args.get('status')
        
        query = EmployeeAdvance.query
        if employee_id:
            query = query.filter_by(employee_id=employee_id)
        if status:
            query = query.filter_by(status=status)
        
        advances = query.order_by(EmployeeAdvance.created_at.desc()).all()
        return jsonify([a.to_dict() for a in advances])
    except Exception as e:
        print(f"Error in get_advances: {str(e)}")
        return jsonify({'error': str(e)}), 500

@advances_bp.route('', methods=['POST'])
def create_advance():
    """Create a new advance with auto-deduction"""
    try:
        data = request.json
        
        # Get worker
        worker = Worker.query.get(data.get('employeeId'))
        if not worker:
            return jsonify({'error': 'Employee not found'}), 404
        
        amount = float(data.get('amount', 0))
        tenure_months = int(data.get('tenureMonths', 1))
        
        # Get monthly salary
        monthly_salary = 0
        if hasattr(worker, 'monthly_salary'):
            monthly_salary = worker.monthly_salary or 0
        elif hasattr(worker, 'salary'):
            monthly_salary = worker.salary or 0
        
        # If no monthly salary, use daily_rate * 26
        if monthly_salary == 0 and hasattr(worker, 'daily_rate'):
            monthly_salary = (worker.daily_rate or 0) * 26
        
        # Validate amount against salary (max 50% of monthly salary)
        max_allowed = monthly_salary * 0.5 if monthly_salary > 0 else amount * 2
        
        if amount > max_allowed and monthly_salary > 0:
            return jsonify({
                'error': f'Advance amount ({amount}) exceeds 50% of monthly salary ({max_allowed:.3f})'
            }), 400
        
        # Create advance
        advance = EmployeeAdvance(
            id=generate_id(),
            employee_id=data.get('employeeId'),
            advance_type_id=data.get('advanceTypeId'),
            advance_number=EmployeeAdvance.generate_advance_number(),
            amount=amount,
            advance_date=datetime.strptime(data.get('advanceDate'), '%Y-%m-%d').date(),
            tenure_months=tenure_months,
            reason=data.get('reason', ''),
            status='active',
            approved_by=data.get('approvedBy', 'System'),
            approved_date=datetime.now().date(),
            notes=data.get('notes', ''),
            paid_amount=0,
            remaining_balance=amount,
            deduction_start_month=data.get('deductionStartMonth'),
            deduction_end_month=data.get('deductionEndMonth')
        )
        
        # Calculate monthly deduction
        advance.monthly_deduction = amount / tenure_months if tenure_months > 0 else amount
        
        db.session.add(advance)
        db.session.commit()
        
        # Generate deduction schedule
        generate_deduction_schedule(advance.id)
        
        return jsonify(advance.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_advance: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400

@advances_bp.route('/<advance_id>', methods=['GET'])
def get_advance(advance_id):
    """Get a single advance"""
    try:
        advance = EmployeeAdvance.query.get_or_404(advance_id)
        return jsonify(advance.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@advances_bp.route('/<advance_id>', methods=['PUT'])
def update_advance(advance_id):
    """Update an advance"""
    try:
        advance = EmployeeAdvance.query.get_or_404(advance_id)
        data = request.json
        
        if 'reason' in data:
            advance.reason = data['reason']
        if 'notes' in data:
            advance.notes = data['notes']
        if 'status' in data:
            advance.status = data['status']
        
        db.session.commit()
        return jsonify(advance.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@advances_bp.route('/<advance_id>', methods=['DELETE'])
def delete_advance(advance_id):
    """Delete an advance"""
    try:
        advance = EmployeeAdvance.query.get_or_404(advance_id)
        
        # Delete all associated deductions
        AdvanceSalaryDeduction.query.filter_by(advance_id=advance_id).delete()
        
        db.session.delete(advance)
        db.session.commit()
        return jsonify({'message': 'Advance deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


# ============================================
# REPAYMENTS
# ============================================

@advances_bp.route('/<advance_id>/repayments', methods=['POST'])
def make_repayment(advance_id):
    """Record a manual repayment"""
    try:
        advance = EmployeeAdvance.query.get_or_404(advance_id)
        data = request.json
        
        amount = float(data.get('amount', 0))
        payment_date = datetime.strptime(data.get('paymentDate'), '%Y-%m-%d').date()
        
        if amount <= 0:
            return jsonify({'error': 'Amount must be greater than 0'}), 400
        
        if amount > advance.remaining_balance:
            return jsonify({'error': f'Amount exceeds remaining balance of {advance.remaining_balance}'}), 400
        
        repayment = AdvanceRepayment(
            id=generate_id(),
            advance_id=advance_id,
            payment_date=payment_date,
            amount=amount,
            payment_method=data.get('paymentMethod', 'cash'),
            reference_number=data.get('referenceNumber'),
            notes=data.get('notes'),
            created_by=data.get('createdBy', 'System')
        )
        
        db.session.add(repayment)
        
        # Update advance balance
        advance.paid_amount = (advance.paid_amount or 0) + amount
        advance.remaining_balance = (advance.amount or 0) - advance.paid_amount
        
        if advance.remaining_balance <= 0:
            advance.status = 'completed'
            advance.remaining_balance = 0
        
        db.session.commit()
        return jsonify(repayment.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in make_repayment: {str(e)}")
        return jsonify({'error': str(e)}), 400

@advances_bp.route('/<advance_id>/repayments', methods=['GET'])
def get_repayments(advance_id):
    """Get all repayments for an advance"""
    try:
        advance = EmployeeAdvance.query.get_or_404(advance_id)
        repayments = advance.repayments.order_by(AdvanceRepayment.payment_date.desc()).all()
        return jsonify([r.to_dict() for r in repayments])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# DEDUCTION MANAGEMENT
# ============================================

def generate_deduction_schedule(advance_id):
    """Generate monthly deduction schedule for an advance"""
    try:
        advance = EmployeeAdvance.query.get(advance_id)
        if not advance:
            return 0
        
        # Clear existing deductions
        AdvanceSalaryDeduction.query.filter_by(advance_id=advance_id).delete()
        
        # Generate monthly deductions
        start_date = datetime.strptime(advance.deduction_start_month, '%Y-%m').date()
        end_date = datetime.strptime(advance.deduction_end_month, '%Y-%m').date()
        
        current = start_date
        month_count = 0
        
        while current <= end_date and month_count < advance.tenure_months:
            month_str = current.strftime('%Y-%m')
            
            deduction = AdvanceSalaryDeduction(
                id=generate_id(),
                advance_id=advance.id,
                employee_id=advance.employee_id,
                month=month_str,
                amount=advance.monthly_deduction,
                deducted=False,
                notes=f'Auto-deduction for {month_str}'
            )
            db.session.add(deduction)
            month_count += 1
            
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        db.session.commit()
        return month_count
    except Exception as e:
        db.session.rollback()
        print(f"Error generating deduction schedule: {str(e)}")
        return 0

@advances_bp.route('/deductions/schedule', methods=['GET'])
def get_deduction_schedule():
    """Get deduction schedule for an employee or advance"""
    try:
        employee_id = request.args.get('employeeId')
        advance_id = request.args.get('advanceId')
        month = request.args.get('month')
        
        query = AdvanceSalaryDeduction.query
        
        if employee_id:
            query = query.filter_by(employee_id=employee_id)
        if advance_id:
            query = query.filter_by(advance_id=advance_id)
        if month:
            query = query.filter_by(month=month)
        
        deductions = query.order_by(AdvanceSalaryDeduction.month).all()
        return jsonify([d.to_dict() for d in deductions])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@advances_bp.route('/deductions/auto-process', methods=['POST'])
def auto_process_deductions():
    """Auto-process all pending deductions for current month"""
    try:
        today = datetime.now()
        current_month = today.strftime('%Y-%m')
        
        # Get all pending deductions for current month
        pending_deductions = AdvanceSalaryDeduction.query.filter_by(
            month=current_month, 
            deducted=False
        ).all()
        
        if not pending_deductions:
            return jsonify({
                'message': f'No pending deductions for {current_month}',
                'processed': 0,
                'totalAmount': 0
            }), 200
        
        processed = 0
        total_amount = 0
        results = []
        
        for deduction in pending_deductions:
            advance = EmployeeAdvance.query.get(deduction.advance_id)
            
            # Skip if advance is not active
            if not advance or advance.status != 'active':
                continue
            
            if deduction.amount <= 0:
                continue
            
            # Process deduction
            deduction.deducted = True
            deduction.deducted_date = today.date()
            processed += 1
            total_amount += deduction.amount
            
            # Update advance balance
            advance.paid_amount = (advance.paid_amount or 0) + deduction.amount
            advance.remaining_balance = (advance.amount or 0) - advance.paid_amount
            
            if advance.remaining_balance <= 0:
                advance.status = 'completed'
                advance.remaining_balance = 0
            
            # Create repayment record
            repayment = AdvanceRepayment(
                id=generate_id(),
                advance_id=advance.id,
                payment_date=today.date(),
                amount=deduction.amount,
                payment_method='salary_deduction',
                notes=f'Auto-deduction for {current_month}',
                created_by='System'
            )
            db.session.add(repayment)
            
            results.append({
                'employee': advance.employee.name if advance.employee else 'Unknown',
                'advanceNumber': advance.advance_number,
                'amount': deduction.amount
            })
        
        db.session.commit()
        
        return jsonify({
            'message': f'Processed {processed} deductions for {current_month}',
            'processed': processed,
            'totalAmount': total_amount,
            'results': results
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error in auto_process_deductions: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ============================================
# SUMMARY
# ============================================

@advances_bp.route('/summary', methods=['GET'])
def get_advance_summary():
    """Get summary statistics for advances"""
    try:
        total_advances = EmployeeAdvance.query.count()
        active_advances = EmployeeAdvance.query.filter_by(status='active').count()
        completed_advances = EmployeeAdvance.query.filter_by(status='completed').count()
        
        total_amount = db.session.query(db.func.sum(EmployeeAdvance.amount)).scalar() or 0
        total_balance = db.session.query(db.func.sum(EmployeeAdvance.remaining_balance)).scalar() or 0
        total_paid = db.session.query(db.func.sum(EmployeeAdvance.paid_amount)).scalar() or 0
        
        return jsonify({
            'totalAdvances': total_advances,
            'activeAdvances': active_advances,
            'completedAdvances': completed_advances,
            'totalAmount': float(total_amount),
            'totalBalance': float(total_balance),
            'totalPaid': float(total_paid),
            'collectionRate': (total_paid / total_amount * 100) if total_amount > 0 else 0
        })
    except Exception as e:
        print(f"Error in get_advance_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500

@advances_bp.route('/employee/<employee_id>/summary', methods=['GET'])
def get_employee_advance_summary(employee_id):
    """Get advance summary for a specific employee"""
    try:
        advances = EmployeeAdvance.query.filter_by(employee_id=employee_id).all()
        
        total_advances = len(advances)
        active_advances = sum(1 for a in advances if a.status == 'active')
        total_amount = sum(a.amount for a in advances)
        total_balance = sum(a.remaining_balance for a in advances)
        total_paid = sum(a.paid_amount for a in advances)
        
        return jsonify({
            'employeeId': employee_id,
            'totalAdvances': total_advances,
            'activeAdvances': active_advances,
            'totalAmount': total_amount,
            'totalBalance': total_balance,
            'totalPaid': total_paid
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500