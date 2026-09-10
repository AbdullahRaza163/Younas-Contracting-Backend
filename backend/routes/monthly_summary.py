# routes/monthly_summary.py
from flask import request, jsonify
from models import MonthlySummary, Entry, Expense, db
from routes import summary_bp
from datetime import datetime
import calendar
import random
import string
import logging
from sqlalchemy import func

logger = logging.getLogger(__name__)

@summary_bp.route('', methods=['GET'])
@summary_bp.route('/', methods=['GET'])
def get_monthly_summaries():
    """Get all monthly summaries"""
    try:
        month = request.args.get('month')
        if month:
            summary = MonthlySummary.get_summary_by_month(month)
            if summary:
                return jsonify(summary.to_dict())
            return jsonify({'error': 'Summary not found for this month'}), 404
        
        # Get all summaries ordered by month descending (newest first)
        summaries = MonthlySummary.query.order_by(MonthlySummary.month.desc()).all()
        result = [s.to_dict() for s in summaries]
        logger.info(f"📊 Returning {len(result)} monthly summaries")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_monthly_summaries: {str(e)}")
        return jsonify({'error': str(e)}), 500

@summary_bp.route('', methods=['POST'])
@summary_bp.route('/', methods=['POST'])
def create_monthly_summary():
    """Create or update a monthly summary"""
    try:
        data = request.json
        month = data.get('month')
        
        if not month:
            return jsonify({'error': 'Month is required'}), 400
        
        # Check if summary exists
        summary = MonthlySummary.get_summary_by_month(month)
        
        if not summary:
            summary = MonthlySummary(
                id=''.join(random.choices(string.ascii_lowercase + string.digits, k=9)),
                month=month
            )
            db.session.add(summary)
        
        # Update fields
        summary.total_revenue = float(data.get('totalRevenue', 0))
        summary.total_labour = float(data.get('totalLabour', 0))
        summary.car_patrol = float(data.get('carPatrol', 0))
        summary.monthly_oh = float(data.get('monthlyOh', 0))
        summary.one_time = float(data.get('oneTime', 0))
        summary.notes = data.get('notes', '')
        
        # Calculate net profit and status
        summary.calculate_net_profit()
        summary.update_status()
        
        db.session.commit()
        
        logger.info(f"✅ Created/Updated monthly summary for {month}")
        return jsonify(summary.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in create_monthly_summary: {str(e)}")
        return jsonify({'error': str(e)}), 400

@summary_bp.route('/calculate/<month>', methods=['POST'])
@summary_bp.route('/calculate/<month>/', methods=['POST'])
def calculate_monthly_summary(month):
    """Calculate monthly summary from entries and expenses - AUTO CALCULATE"""
    try:
        from models import Entry, Expense, Attendance, Worker
        from datetime import datetime as dt
        
        logger.info(f"📊 Calculating summary for month: {month}")
        
        # Parse month
        year, month_num = month.split('-')
        start_date = dt.strptime(f"{year}-{month_num}-01", '%Y-%m-%d')
        last_day = calendar.monthrange(int(year), int(month_num))[1]
        end_date = dt.strptime(f"{year}-{month_num}-{last_day}", '%Y-%m-%d')
        
        logger.info(f"📅 Date range: {start_date} to {end_date}")
        
        # ===== 1. CALCULATE FROM ENTRIES =====
        entries = Entry.query.filter(
            Entry.date >= start_date,
            Entry.date <= end_date
        ).all()
        
        logger.info(f"📊 Found {len(entries)} entries for {month}")
        
        total_revenue = sum(e.kamai or 0 for e in entries)
        total_labour = sum(e.labour or 0 for e in entries)
        total_one_time = sum(e.one_time or 0 for e in entries)
        total_overhead = sum(e.overhead or 0 for e in entries)
        total_material = sum(e.material_cost or 0 for e in entries)
        total_equipment = sum(e.equipment_cost or 0 for e in entries)
        total_transport = sum(e.transport_cost or 0 for e in entries)
        total_other_expense = sum(e.other_expense or 0 for e in entries)
        
        # ===== 2. CALCULATE FROM EXPENSES =====
        expenses = Expense.query.filter(
            Expense.date >= start_date,
            Expense.date <= end_date
        ).all()
        
        logger.info(f"📊 Found {len(expenses)} expenses for {month}")
        
        # Categorize expenses
        expense_car_patrol = sum(e.amount for e in expenses if e.category == 'car_patrol')
        expense_overhead = sum(e.amount for e in expenses if e.category == 'overhead')
        expense_material = sum(e.amount for e in expenses if e.category == 'material')
        expense_equipment = sum(e.amount for e in expenses if e.category == 'equipment')
        expense_transport = sum(e.amount for e in expenses if e.category == 'transport')
        expense_other = sum(e.amount for e in expenses if e.category == 'other')
        
        # ===== 3. CALCULATE FROM ATTENDANCE (Labour cost) =====
        # Get all attendance for the month
        attendances = Attendance.query.filter(
            Attendance.date >= start_date,
            Attendance.date <= end_date,
            Attendance.present == True
        ).all()
        
        logger.info(f"📊 Found {len(attendances)} attendance records for {month}")
        
        # Calculate labour from attendance (if no entries labour is available)
        total_labour_from_attendance = 0
        if attendances:
            for att in attendances:
                # Get worker's daily rate
                worker = Worker.query.get(att.worker_id)
                if worker:
                    # Calculate wage based on hours worked
                    hours = att.total_hours or att.normal_hours or 8
                    hourly_rate = worker.hourly_rate or (worker.daily_rate / 8)
                    total_labour_from_attendance += hours * hourly_rate
        
        # Use the larger of labour from entries or attendance
        if total_labour == 0 and total_labour_from_attendance > 0:
            total_labour = total_labour_from_attendance
            logger.info(f"💼 Using labour from attendance: {total_labour}")
        
        # ===== 4. COMBINE ALL TOTALS =====
        final_car_patrol = expense_car_patrol  # From expenses
        final_monthly_oh = expense_overhead + total_overhead  # From expenses + entries overhead
        final_one_time = (
            total_one_time + 
            total_material + expense_material + 
            total_equipment + expense_equipment + 
            total_transport + expense_transport + 
            total_other_expense + expense_other
        )
        
        logger.info(f"💰 Revenue: {total_revenue}")
        logger.info(f"👷 Labour: {total_labour}")
        logger.info(f"🚗 Car Patrol: {final_car_patrol}")
        logger.info(f"🏢 Monthly OH: {final_monthly_oh}")
        logger.info(f"📦 One Time: {final_one_time}")
        
        # ===== 5. GET OR CREATE SUMMARY =====
        summary = MonthlySummary.get_summary_by_month(month)
        if not summary:
            summary = MonthlySummary(
                id=''.join(random.choices(string.ascii_lowercase + string.digits, k=9)),
                month=month
            )
            db.session.add(summary)
        
        # Update summary
        summary.total_revenue = total_revenue
        summary.total_labour = total_labour
        summary.car_patrol = final_car_patrol
        summary.monthly_oh = final_monthly_oh
        summary.one_time = final_one_time
        
        # Calculate net profit and status
        summary.calculate_net_profit()
        summary.update_status()
        
        # Add notes
        summary.notes = f"Auto-calculated from {len(entries)} entries, {len(expenses)} expenses, {len(attendances)} attendance records"
        
        db.session.commit()
        
        logger.info(f"✅ Calculated summary for {month}: Net = {summary.net_profit}")
        return jsonify(summary.to_dict())
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in calculate_monthly_summary: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400

@summary_bp.route('/calculate-all', methods=['POST'])
@summary_bp.route('/calculate-all/', methods=['POST'])
def calculate_all_monthly_summaries():
    """Calculate summaries for all months that have data"""
    try:
        from models import Entry, Expense, Attendance
        
        # Get all distinct months from entries, expenses, and attendance
        months = set()
        
        # From entries
        entry_months = db.session.query(func.distinct(func.date_trunc('month', Entry.date))).all()
        for m in entry_months:
            if m[0]:
                months.add(m[0].strftime('%Y-%m'))
        
        # From expenses
        expense_months = db.session.query(func.distinct(func.date_trunc('month', Expense.date))).all()
        for m in expense_months:
            if m[0]:
                months.add(m[0].strftime('%Y-%m'))
        
        # From attendance
        attendance_months = db.session.query(func.distinct(func.date_trunc('month', Attendance.date))).all()
        for m in attendance_months:
            if m[0]:
                months.add(m[0].strftime('%Y-%m'))
        
        months = sorted(list(months))
        logger.info(f"📊 Found {len(months)} months with data")
        
        results = []
        for month in months:
            try:
                # Call calculate function for each month
                response = calculate_monthly_summary(month)
                if response:
                    # Get the response data
                    if hasattr(response, 'get_json'):
                        data = response.get_json()
                    else:
                        data = response
                    results.append({
                        'month': month,
                        'status': 'success',
                        'data': data
                    })
            except Exception as e:
                results.append({
                    'month': month,
                    'status': 'error',
                    'error': str(e)
                })
        
        return jsonify({
            'total': len(results),
            'success': len([r for r in results if r['status'] == 'success']),
            'failed': len([r for r in results if r['status'] == 'error']),
            'results': results
        })
    except Exception as e:
        logger.error(f"Error in calculate_all: {str(e)}")
        return jsonify({'error': str(e)}), 400

@summary_bp.route('/auto-update', methods=['POST'])
@summary_bp.route('/auto-update/', methods=['POST'])
def auto_update_current_month():
    """Auto-update the current month's summary"""
    try:
        now = datetime.now()
        current_month = now.strftime('%Y-%m')
        
        logger.info(f"🔄 Auto-updating summary for current month: {current_month}")
        
        response = calculate_monthly_summary(current_month)
        
        if response:
            return jsonify({
                'message': f'✅ Auto-updated summary for {current_month}',
                'data': response.get_json() if hasattr(response, 'get_json') else response
            })
        else:
            return jsonify({'error': 'Failed to auto-update'}), 400
            
    except Exception as e:
        logger.error(f"Error in auto_update: {str(e)}")
        return jsonify({'error': str(e)}), 400

@summary_bp.route('/<summary_id>', methods=['PUT'])
@summary_bp.route('/<summary_id>/', methods=['PUT'])
def update_monthly_summary(summary_id):
    """Update a monthly summary manually"""
    try:
        summary = MonthlySummary.query.get_or_404(summary_id)
        data = request.json
        
        if 'totalRevenue' in data:
            summary.total_revenue = float(data['totalRevenue'])
        if 'totalLabour' in data:
            summary.total_labour = float(data['totalLabour'])
        if 'carPatrol' in data:
            summary.car_patrol = float(data['carPatrol'])
        if 'monthlyOh' in data:
            summary.monthly_oh = float(data['monthlyOh'])
        if 'oneTime' in data:
            summary.one_time = float(data['oneTime'])
        if 'notes' in data:
            summary.notes = data['notes']
        
        summary.calculate_net_profit()
        summary.update_status()
        
        db.session.commit()
        logger.info(f"✅ Updated summary {summary_id}")
        return jsonify(summary.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in update_monthly_summary: {str(e)}")
        return jsonify({'error': str(e)}), 400

@summary_bp.route('/<summary_id>', methods=['DELETE'])
@summary_bp.route('/<summary_id>/', methods=['DELETE'])
def delete_monthly_summary(summary_id):
    """Delete a monthly summary"""
    try:
        summary = MonthlySummary.query.get_or_404(summary_id)
        db.session.delete(summary)
        db.session.commit()
        logger.info(f"✅ Deleted summary {summary_id}")
        return jsonify({'message': 'Monthly summary deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in delete_monthly_summary: {str(e)}")
        return jsonify({'error': str(e)}), 400