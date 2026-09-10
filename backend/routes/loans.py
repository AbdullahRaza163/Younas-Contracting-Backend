# routes/loans.py - Fixed version
from flask import request, jsonify
from models import db, LoanType, EmployeeLoan, LoanRepayment, SalaryDeduction, LoanDeduction, Worker
from utils.helpers import generate_id
from routes import loans_bp
from datetime import datetime, timedelta
import random
import string

# ============================================
# LOAN TYPES
# ============================================

@loans_bp.route('/types', methods=['GET'])
def get_loan_types():
    try:
        types = LoanType.query.filter_by(is_active=True).all()
        return jsonify([t.to_dict() for t in types])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@loans_bp.route('/types', methods=['POST'])
def create_loan_type():
    try:
        data = request.json
        loan_type = LoanType(
            id=generate_id(),
            name=data.get('name'),
            description=data.get('description'),
            max_amount=float(data.get('maxAmount', 0)),
            interest_rate=float(data.get('interestRate', 0)),
            default_tenure=int(data.get('defaultTenure', 6))
        )
        db.session.add(loan_type)
        db.session.commit()
        return jsonify(loan_type.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@loans_bp.route('/types/<type_id>', methods=['PUT'])
def update_loan_type(type_id):
    try:
        loan_type = LoanType.query.get_or_404(type_id)
        data = request.json
        
        if 'name' in data:
            loan_type.name = data['name']
        if 'description' in data:
            loan_type.description = data['description']
        if 'maxAmount' in data:
            loan_type.max_amount = float(data['maxAmount'])
        if 'interestRate' in data:
            loan_type.interest_rate = float(data['interestRate'])
        if 'defaultTenure' in data:
            loan_type.default_tenure = int(data['defaultTenure'])
        if 'isActive' in data:
            loan_type.is_active = data['isActive']
        
        db.session.commit()
        return jsonify(loan_type.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@loans_bp.route('/types/<type_id>', methods=['DELETE'])
def delete_loan_type(type_id):
    try:
        loan_type = LoanType.query.get_or_404(type_id)
        db.session.delete(loan_type)
        db.session.commit()
        return jsonify({'message': 'Loan type deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# EMPLOYEE LOANS
# ============================================

@loans_bp.route('', methods=['GET'])
def get_loans():
    try:
        employee_id = request.args.get('employeeId')
        status = request.args.get('status')
        
        query = EmployeeLoan.query
        if employee_id:
            query = query.filter_by(employee_id=employee_id)
        if status:
            query = query.filter_by(status=status)
        
        loans = query.order_by(EmployeeLoan.created_at.desc()).all()
        return jsonify([l.to_dict() for l in loans])
    except Exception as e:
        print(f"Error in get_loans: {str(e)}")
        return jsonify({'error': str(e)}), 500

@loans_bp.route('', methods=['POST'])
def create_loan():
    try:
        data = request.json
        
        # Get worker
        worker = Worker.query.get(data.get('employeeId'))
        if not worker:
            return jsonify({'error': 'Employee not found'}), 404
        
        # Get loan type
        loan_type = LoanType.query.get(data.get('loanTypeId'))
        
        amount = float(data.get('amount', 0))
        tenure_months = int(data.get('tenureMonths', 6))
        interest_rate = float(data.get('interestRate', 0))
        
        loan = EmployeeLoan(
            id=generate_id(),
            employee_id=data.get('employeeId'),
            loan_type_id=data.get('loanTypeId'),
            loan_number=EmployeeLoan.generate_loan_number(),
            amount=amount,
            loan_date=datetime.strptime(data.get('loanDate'), '%Y-%m-%d').date(),
            tenure_months=tenure_months,
            interest_rate=interest_rate,
            purpose=data.get('purpose'),
            status='active',
            approved_by=data.get('approvedBy'),
            approved_date=datetime.now().date(),
            notes=data.get('notes'),
            paid_amount=0,
            remaining_balance=0
        )
        
        # Calculate installment
        loan.calculate_installment()
        
        db.session.add(loan)
        db.session.commit()
        return jsonify(loan.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_loan: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400

@loans_bp.route('/<loan_id>', methods=['GET'])
def get_loan(loan_id):
    try:
        loan = EmployeeLoan.query.get_or_404(loan_id)
        return jsonify(loan.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@loans_bp.route('/<loan_id>', methods=['PUT'])
def update_loan(loan_id):
    try:
        loan = EmployeeLoan.query.get_or_404(loan_id)
        data = request.json
        
        if 'purpose' in data:
            loan.purpose = data['purpose']
        if 'notes' in data:
            loan.notes = data['notes']
        if 'status' in data:
            loan.status = data['status']
        
        db.session.commit()
        return jsonify(loan.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@loans_bp.route('/<loan_id>', methods=['DELETE'])
def delete_loan(loan_id):
    try:
        loan = EmployeeLoan.query.get_or_404(loan_id)
        db.session.delete(loan)
        db.session.commit()
        return jsonify({'message': 'Loan deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# REPAYMENTS
# ============================================

@loans_bp.route('/<loan_id>/repayments', methods=['POST'])
def make_repayment(loan_id):
    try:
        loan = EmployeeLoan.query.get_or_404(loan_id)
        data = request.json
        
        amount = float(data.get('amount', 0))
        payment_date = datetime.strptime(data.get('paymentDate'), '%Y-%m-%d').date()
        
        if amount <= 0:
            return jsonify({'error': 'Amount must be greater than 0'}), 400
        
        if amount > loan.remaining_balance:
            return jsonify({'error': f'Amount exceeds remaining balance of {loan.remaining_balance}'}), 400
        
        repayment = LoanRepayment(
            id=generate_id(),
            loan_id=loan_id,
            payment_date=payment_date,
            amount=amount,
            principal=amount,
            interest=0,
            payment_method=data.get('paymentMethod', 'cash'),
            reference_number=data.get('referenceNumber'),
            notes=data.get('notes'),
            created_by=data.get('createdBy', 'System')
        )
        
        db.session.add(repayment)
        
        # Update loan balance
        loan.paid_amount = (loan.paid_amount or 0) + amount
        loan.remaining_balance = (loan.total_payable or loan.amount) - loan.paid_amount
        
        if loan.remaining_balance <= 0:
            loan.status = 'completed'
            loan.remaining_balance = 0
        
        db.session.commit()
        return jsonify(repayment.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in make_repayment: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400

@loans_bp.route('/<loan_id>/repayments', methods=['GET'])
def get_repayments(loan_id):
    try:
        loan = EmployeeLoan.query.get_or_404(loan_id)
        repayments = loan.repayments.order_by(LoanRepayment.payment_date.desc()).all()
        return jsonify([r.to_dict() for r in repayments])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# DEDUCTIONS
# ============================================

@loans_bp.route('/<loan_id>/deductions', methods=['POST'])
def create_deduction(loan_id):
    try:
        loan = EmployeeLoan.query.get_or_404(loan_id)
        data = request.json
        
        deduction = LoanDeduction(
            id=generate_id(),
            loan_id=loan_id,
            month=data.get('month'),
            amount=float(data.get('amount', 0)),
            notes=data.get('notes')
        )
        
        db.session.add(deduction)
        db.session.commit()
        return jsonify(deduction.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@loans_bp.route('/<loan_id>/deductions', methods=['GET'])
def get_deductions(loan_id):
    try:
        loan = EmployeeLoan.query.get_or_404(loan_id)
        deductions = loan.deductions.order_by(LoanDeduction.month.desc()).all()
        return jsonify([d.to_dict() for d in deductions])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# SUMMARY
# ============================================

@loans_bp.route('/summary', methods=['GET'])
def get_loan_summary():
    try:
        total_loans = EmployeeLoan.query.count()
        active_loans = EmployeeLoan.query.filter_by(status='active').count()
        completed_loans = EmployeeLoan.query.filter_by(status='completed').count()
        
        total_amount = db.session.query(db.func.sum(EmployeeLoan.amount)).scalar() or 0
        total_balance = db.session.query(db.func.sum(EmployeeLoan.remaining_balance)).scalar() or 0
        total_paid = db.session.query(db.func.sum(EmployeeLoan.paid_amount)).scalar() or 0
        
        return jsonify({
            'totalLoans': total_loans,
            'activeLoans': active_loans,
            'completedLoans': completed_loans,
            'totalAmount': float(total_amount),
            'totalBalance': float(total_balance),
            'totalPaid': float(total_paid),
            'collectionRate': (total_paid / total_amount * 100) if total_amount > 0 else 0
        })
    except Exception as e:
        print(f"Error in get_loan_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500

    # routes/loans.py - Add auto-deduction endpoints

# ============================================
# AUTO DEDUCTION - Salary Deduction Management
# ============================================

@loans_bp.route('/<loan_id>/auto-deduct', methods=['POST'])
def enable_auto_deduction(loan_id):
    """Enable auto-deduction for a loan"""
    try:
        loan = EmployeeLoan.query.get_or_404(loan_id)
        data = request.json
        
        loan.auto_deduct = True
        loan.deduction_start_month = data.get('startMonth')
        loan.deduction_end_month = data.get('endMonth')
        
        db.session.commit()
        
        # Generate deduction schedule
        generate_deduction_schedule(loan_id)
        
        return jsonify({
            'message': 'Auto-deduction enabled successfully',
            'loan': loan.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error in enable_auto_deduction: {str(e)}")
        return jsonify({'error': str(e)}), 400

@loans_bp.route('/<loan_id>/auto-deduct/disable', methods=['POST'])
def disable_auto_deduction(loan_id):
    """Disable auto-deduction for a loan"""
    try:
        loan = EmployeeLoan.query.get_or_404(loan_id)
        
        loan.auto_deduct = False
        
        db.session.commit()
        return jsonify({
            'message': 'Auto-deduction disabled successfully',
            'loan': loan.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@loans_bp.route('/<loan_id>/deductions/generate', methods=['POST'])
def generate_deduction_schedule(loan_id):
    """Generate monthly deduction schedule for a loan"""
    try:
        loan = EmployeeLoan.query.get_or_404(loan_id)
        
        if not loan.auto_deduct:
            return jsonify({'error': 'Auto-deduction is not enabled for this loan'}), 400
        
        # Clear existing deductions
        SalaryDeduction.query.filter_by(loan_id=loan_id).delete()
        
        # Generate monthly deductions
        start_date = datetime.strptime(loan.deduction_start_month, '%Y-%m').date()
        end_date = datetime.strptime(loan.deduction_end_month, '%Y-%m').date()
        
        current = start_date
        month_count = 0
        
        while current <= end_date and month_count < loan.tenure_months:
            month_str = current.strftime('%Y-%m')
            
            deduction = SalaryDeduction(
                id=generate_id(),
                employee_id=loan.employee_id,
                loan_id=loan.id,
                month=month_str,
                amount=loan.monthly_installment,
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
        
        return jsonify({
            'message': f'Generated {month_count} monthly deductions',
            'count': month_count
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error in generate_deduction_schedule: {str(e)}")
        return jsonify({'error': str(e)}), 400

@loans_bp.route('/deductions/schedule', methods=['GET'])
def get_deduction_schedule():
    """Get deduction schedule for an employee or loan"""
    try:
        employee_id = request.args.get('employeeId')
        loan_id = request.args.get('loanId')
        month = request.args.get('month')
        
        query = SalaryDeduction.query
        
        if employee_id:
            query = query.filter_by(employee_id=employee_id)
        if loan_id:
            query = query.filter_by(loan_id=loan_id)
        if month:
            query = query.filter_by(month=month)
        
        deductions = query.order_by(SalaryDeduction.month).all()
        return jsonify([d.to_dict() for d in deductions])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@loans_bp.route('/deductions/process/<month>', methods=['POST'])
def process_monthly_deductions(month):
    """Process all salary deductions for a specific month"""
    try:
        # Get all pending deductions for the month
        deductions = SalaryDeduction.query.filter_by(month=month, deducted=False).all()
        
        processed = 0
        total_amount = 0
        
        for deduction in deductions:
            loan = EmployeeLoan.query.get(deduction.loan_id)
            if loan and loan.status == 'active':
                # Process deduction
                deduction.deducted = True
                deduction.deducted_date = datetime.now().date()
                processed += 1
                total_amount += deduction.amount
                
                # Update loan balance
                loan.paid_amount = (loan.paid_amount or 0) + deduction.amount
                loan.remaining_balance = (loan.total_payable or loan.amount) - loan.paid_amount
                
                if loan.remaining_balance <= 0:
                    loan.status = 'completed'
                    loan.remaining_balance = 0
        
        db.session.commit()
        
        return jsonify({
            'message': f'Processed {processed} deductions for {month}',
            'processed': processed,
            'totalAmount': total_amount
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error in process_monthly_deductions: {str(e)}")
        return jsonify({'error': str(e)}), 400

@loans_bp.route('/deductions/employee/<employee_id>/summary', methods=['GET'])
def get_employee_deduction_summary(employee_id):
    """Get deduction summary for an employee"""
    try:
        # Get all deductions for employee
        deductions = SalaryDeduction.query.filter_by(employee_id=employee_id).all()
        
        total_deducted = sum(d.amount for d in deductions if d.deducted)
        total_pending = sum(d.amount for d in deductions if not d.deducted)
        
        # Get active loans with auto-deduction
        active_loans = EmployeeLoan.query.filter_by(
            employee_id=employee_id,
            status='active',
            auto_deduct=True
        ).all()
        
        return jsonify({
            'employeeId': employee_id,
            'employeeName': deductions[0].employee.name if deductions else 'Unknown',
            'totalDeducted': total_deducted,
            'totalPending': total_pending,
            'activeLoans': [l.to_dict() for l in active_loans],
            'deductionCount': len(deductions),
            'pendingCount': sum(1 for d in deductions if not d.deducted)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    # routes/loans.py - Add auto-process functionality

# routes/loans.py - Update the auto_process_deductions function

@loans_bp.route('/deductions/auto-process', methods=['POST'])
def auto_process_deductions():
    """Auto-process all pending deductions for current month"""
    try:
        today = datetime.now()
        current_month = today.strftime('%Y-%m')
        
        # Get all pending deductions for current month
        pending_deductions = SalaryDeduction.query.filter_by(
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
            loan = EmployeeLoan.query.get(deduction.loan_id)
            
            # Skip if loan is not active or already completed
            if not loan or loan.status != 'active':
                continue
            
            # Check if deduction amount is valid
            if deduction.amount <= 0:
                continue
            
            # Process deduction
            deduction.deducted = True
            deduction.deducted_date = today.date()
            processed += 1
            total_amount += deduction.amount
            
            # Update loan balance
            loan.paid_amount = (loan.paid_amount or 0) + deduction.amount
            loan.remaining_balance = (loan.total_payable or loan.amount) - loan.paid_amount
            
            # Check if loan is completed
            if loan.remaining_balance <= 0:
                loan.status = 'completed'
                loan.remaining_balance = 0
            
            # 🔥 FIX: Create repayment record with salary_deduction method
            repayment = LoanRepayment(
                id=generate_id(),
                loan_id=loan.id,
                payment_date=today.date(),
                amount=deduction.amount,
                principal=deduction.amount,
                interest=0,
                payment_method='salary_deduction',  # ← SET TO salary_deduction
                notes=f'Auto-deduction for {current_month}',
                created_by='System'
            )
            db.session.add(repayment)
            
            results.append({
                'employee': loan.employee.name if loan.employee else 'Unknown',
                'loanNumber': loan.loan_number,
                'amount': deduction.amount,
                'paymentMethod': 'salary_deduction'
            })
            
            # Generate next month's deduction if loan is still active
            if loan.status == 'active':
                generate_next_month_deduction(loan.id)
        
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
def generate_next_month_deduction(loan_id):
    """Generate next month's deduction for a loan"""
    try:
        loan = EmployeeLoan.query.get(loan_id)
        if not loan or loan.status != 'active':
            return
        
        # Calculate next month
        today = datetime.now()
        next_month = today.replace(day=28) + timedelta(days=4)
        next_month_str = next_month.strftime('%Y-%m')
        
        # Check if deduction already exists for next month
        existing = SalaryDeduction.query.filter_by(
            loan_id=loan_id,
            month=next_month_str
        ).first()
        
        if existing:
            return
        
        # Check if we should continue deductions (within end month)
        if loan.deduction_end_month and next_month_str > loan.deduction_end_month:
            return
        
        # Check if loan is fully paid
        if loan.remaining_balance <= 0:
            return
        
        # Create next month's deduction
        deduction = SalaryDeduction(
            id=generate_id(),
            employee_id=loan.employee_id,
            loan_id=loan.id,
            month=next_month_str,
            amount=min(loan.monthly_installment, loan.remaining_balance),
            deducted=False,
            notes=f'Auto-deduction for {next_month_str}'
        )
        db.session.add(deduction)
        
        return deduction
    except Exception as e:
        print(f"Error generating next month deduction: {str(e)}")
        return None