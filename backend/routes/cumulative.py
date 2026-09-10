# routes/cumulative.py
from flask import request, jsonify
from models import CumulativeTracker, Entry, MonthlyOverhead, Site, db
from utils.helpers import generate_id
from routes import cumulative_bp
from datetime import datetime
import calendar
from sqlalchemy import func, extract

# ✅ Base route - uses '' because blueprint prefix is /api/cumulative-tracker
@cumulative_bp.route('', methods=['GET', 'OPTIONS'])
def get_cumulative_tracker():
    """Get all cumulative tracker records"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'OK'})
        return response, 200
    
    try:
        month = request.args.get('month')
        query = CumulativeTracker.query
        
        if month:
            # ✅ Fix: Use EXTRACT or TO_CHAR for PostgreSQL date comparison
            # Method 1: Use EXTRACT (more portable)
            year, month_num = month.split('-')
            query = query.filter(
                extract('year', CumulativeTracker.date) == int(year),
                extract('month', CumulativeTracker.date) == int(month_num)
            )
            
            # Method 2: Use date range (alternative)
            # from datetime import datetime
            # start_date = datetime.strptime(f"{month}-01", "%Y-%m-%d")
            # if month_num == '12':
            #     end_date = datetime.strptime(f"{int(year)+1}-01-01", "%Y-%m-%d")
            # else:
            #     end_date = datetime.strptime(f"{year}-{int(month_num)+1}-01", "%Y-%m-%d")
            # query = query.filter(
            #     CumulativeTracker.date >= start_date,
            #     CumulativeTracker.date < end_date
            # )
        
        trackers = query.order_by(CumulativeTracker.date.asc()).all()
        return jsonify([t.to_dict() for t in trackers])
    except Exception as e:
        print(f"Error in get_cumulative_tracker: {str(e)}")
        return jsonify({'error': str(e)}), 500

@cumulative_bp.route('', methods=['POST'])
def create_cumulative_tracker():
    """Create a new cumulative tracker record"""
    try:
        data = request.json
        
        if not data.get('date'):
            return jsonify({'error': 'Date is required'}), 400
        
        # Check if entry already exists for this date
        existing = CumulativeTracker.query.filter_by(date=data.get('date')).first()
        if existing:
            # Update existing instead of creating new
            existing.revenue = float(data.get('revenue', 0))
            existing.labour = float(data.get('labour', 0))
            existing.oh_share = float(data.get('ohShare', 0))
            existing.net = float(data.get('net', 0))
            existing.notes = data.get('notes', '')
            existing.update_cumulative()
            db.session.commit()
            return jsonify(existing.to_dict()), 200
        
        tracker = CumulativeTracker(
            id=generate_id(),
            date=datetime.strptime(data.get('date'), '%Y-%m-%d').date(),
            revenue=float(data.get('revenue', 0)),
            labour=float(data.get('labour', 0)),
            oh_share=float(data.get('ohShare', 0)),
            net=float(data.get('net', 0)),
            notes=data.get('notes', '')
        )
        
        tracker.update_cumulative()
        
        db.session.add(tracker)
        db.session.commit()
        return jsonify(tracker.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_cumulative_tracker: {str(e)}")
        return jsonify({'error': str(e)}), 400

@cumulative_bp.route('/<tracker_id>', methods=['GET'])
def get_cumulative_tracker_by_id(tracker_id):
    """Get a specific cumulative tracker record"""
    try:
        tracker = CumulativeTracker.query.get_or_404(tracker_id)
        return jsonify(tracker.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@cumulative_bp.route('/<tracker_id>', methods=['PUT'])
def update_cumulative_tracker(tracker_id):
    """Update a cumulative tracker record"""
    try:
        tracker = CumulativeTracker.query.get_or_404(tracker_id)
        data = request.json
        
        if 'revenue' in data:
            tracker.revenue = float(data['revenue'])
        if 'labour' in data:
            tracker.labour = float(data['labour'])
        if 'ohShare' in data:
            tracker.oh_share = float(data['ohShare'])
        if 'net' in data:
            tracker.net = float(data['net'])
        if 'notes' in data:
            tracker.notes = data['notes']
        
        tracker.update_cumulative()
        
        db.session.commit()
        return jsonify(tracker.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_cumulative_tracker: {str(e)}")
        return jsonify({'error': str(e)}), 400

@cumulative_bp.route('/<tracker_id>', methods=['DELETE'])
def delete_cumulative_tracker(tracker_id):
    """Delete a cumulative tracker record"""
    try:
        tracker = CumulativeTracker.query.get_or_404(tracker_id)
        db.session.delete(tracker)
        db.session.commit()
        return jsonify({'message': 'Tracker record deleted successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error in delete_cumulative_tracker: {str(e)}")
        return jsonify({'error': str(e)}), 400

@cumulative_bp.route('/calculate', methods=['POST', 'OPTIONS'])
def calculate_cumulative():
    """Auto-calculate cumulative tracker from existing data"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'OK'})
        return response, 200
    
    try:
        data = request.json
        month = data.get('month')
        
        if not month:
            return jsonify({'error': 'Month is required'}), 400
        
        year, month_num = month.split('-')
        start_date = f"{year}-{month_num}-01"
        
        last_day = calendar.monthrange(int(year), int(month_num))[1]
        end_date = f"{year}-{month_num}-{last_day}"
        
        # ✅ Fix: Use date range instead of LIKE
        from datetime import datetime as dt
        start_dt = dt.strptime(start_date, '%Y-%m-%d')
        end_dt = dt.strptime(end_date, '%Y-%m-%d')
        
        entries = Entry.query.filter(
            Entry.date >= start_dt,
            Entry.date <= end_dt
        ).all()
        
        if not entries:
            return jsonify({'message': 'No entries found for this month', 'calculated': False}), 200
        
        # Calculate daily totals from entries
        daily_totals = {}
        for entry in entries:
            date_str = entry.date.isoformat() if entry.date else None
            if not date_str:
                continue
                
            if date_str not in daily_totals:
                daily_totals[date_str] = {
                    'date': date_str,
                    'revenue': 0,
                    'labour': 0,
                    'oh_share': 0,
                    'net': 0,
                    'notes': f'Auto-calculated from {len(entries)} entries'
                }
            
            daily_totals[date_str]['revenue'] += float(entry.kamai or 0)
            daily_totals[date_str]['labour'] += float(entry.labour or 0)
        
        # Get monthly overhead for OH share
        monthly_overheads = MonthlyOverhead.query.filter_by(month=month).all()
        total_oh = sum(float(o.amount or 0) for o in monthly_overheads)
        
        sites_count = Site.query.filter_by(active=True).count() or 1
        daily_oh_share = total_oh / (sites_count * 26) if sites_count * 26 > 0 else 0
        
        # Add OH share to daily totals
        for date_str in daily_totals:
            daily_totals[date_str]['oh_share'] = daily_oh_share
            daily_totals[date_str]['net'] = (
                daily_totals[date_str]['revenue'] - 
                daily_totals[date_str]['labour'] - 
                daily_totals[date_str]['oh_share']
            )
        
        sorted_dates = sorted(daily_totals.keys())
        
        # Calculate cumulative
        cumulative = 0
        created_count = 0
        updated_count = 0
        
        # Get previous month's cumulative
        prev_month = f"{year}-{str(int(month_num) - 1).zfill(2)}"
        prev_month_start = f"{year}-{str(int(month_num) - 1).zfill(2)}-01"
        prev_month_end = f"{year}-{str(int(month_num) - 1).zfill(2)}-{calendar.monthrange(int(year), int(month_num)-1)[1]}"
        
        prev_tracker = CumulativeTracker.query.filter(
            CumulativeTracker.date >= dt.strptime(prev_month_start, '%Y-%m-%d'),
            CumulativeTracker.date <= dt.strptime(prev_month_end, '%Y-%m-%d')
        ).order_by(CumulativeTracker.date.desc()).first()
        
        if prev_tracker:
            cumulative = prev_tracker.cumulative
        
        for date_str in sorted_dates:
            day_data = daily_totals[date_str]
            net = day_data['revenue'] - day_data['labour'] - day_data['oh_share']
            cumulative += net
            
            status = '✅ Profit' if cumulative > 0 else '❌ Loss' if cumulative < 0 else '⚖️ Barabar'
            
            # Check if entry exists for this date
            existing = CumulativeTracker.query.filter_by(date=date_str).first()
            
            if existing:
                # Update existing entry
                existing.revenue = day_data['revenue']
                existing.labour = day_data['labour']
                existing.oh_share = day_data['oh_share']
                existing.net = net
                existing.cumulative = cumulative
                existing.status = status
                existing.notes = day_data['notes']
                updated_count += 1
            else:
                # Create new entry
                tracker = CumulativeTracker(
                    id=generate_id(),
                    date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                    revenue=day_data['revenue'],
                    labour=day_data['labour'],
                    oh_share=day_data['oh_share'],
                    net=net,
                    cumulative=cumulative,
                    status=status,
                    notes=day_data['notes']
                )
                db.session.add(tracker)
                created_count += 1
        
        db.session.commit()
        
        return jsonify({
            'message': f'Cumulative tracker calculated successfully',
            'created': created_count,
            'updated': updated_count,
            'total': len(sorted_dates)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error calculating cumulative: {str(e)}")
        return jsonify({'error': str(e)}), 500

@cumulative_bp.route('/latest', methods=['GET'])
def get_latest_tracker():
    """Get the latest cumulative tracker record"""
    try:
        tracker = CumulativeTracker.get_latest_tracker()
        if tracker:
            return jsonify(tracker.to_dict())
        return jsonify({'message': 'No tracker records found'}), 404
    except Exception as e:
        print(f"Error in get_latest_tracker: {str(e)}")
        return jsonify({'error': str(e)}), 500

@cumulative_bp.route('/test', methods=['GET'])
def test_cumulative():
    """Test route to verify blueprint is working"""
    return jsonify({'message': 'Cumulative blueprint is working!'}), 200

@cumulative_bp.route('/auto-calculate', methods=['POST'])
def auto_calculate_all():
    """Auto-calculate cumulative tracker for all months with data"""
    try:
        from sqlalchemy import func, extract
        
        # Get all distinct months from entries using EXTRACT
        months = db.session.query(
            func.concat(
                extract('year', Entry.date),
                '-',
                func.lpad(extract('month', Entry.date).cast(db.String), 2, '0')
            ).label('month')
        ).distinct().order_by('month').all()
        
        results = []
        for month_tuple in months:
            month = month_tuple[0]
            try:
                year, month_num = month.split('-')
                start_date = f"{year}-{month_num}-01"
                last_day = calendar.monthrange(int(year), int(month_num))[1]
                end_date = f"{year}-{month_num}-{last_day}"
                
                from datetime import datetime as dt
                start_dt = dt.strptime(start_date, '%Y-%m-%d')
                end_dt = dt.strptime(end_date, '%Y-%m-%d')
                
                entries = Entry.query.filter(
                    Entry.date >= start_dt,
                    Entry.date <= end_dt
                ).all()
                
                if entries:
                    # Calculate for this month using the same logic
                    daily_totals = {}
                    for entry in entries:
                        date_str = entry.date.isoformat() if entry.date else None
                        if not date_str:
                            continue
                        if date_str not in daily_totals:
                            daily_totals[date_str] = {
                                'date': date_str,
                                'revenue': 0,
                                'labour': 0,
                                'oh_share': 0,
                                'net': 0,
                                'notes': f'Auto-calculated from {len(entries)} entries'
                            }
                        daily_totals[date_str]['revenue'] += float(entry.kamai or 0)
                        daily_totals[date_str]['labour'] += float(entry.labour or 0)
                    
                    # Get monthly overhead
                    monthly_overheads = MonthlyOverhead.query.filter_by(month=month).all()
                    total_oh = sum(float(o.amount or 0) for o in monthly_overheads)
                    sites_count = Site.query.filter_by(active=True).count() or 1
                    daily_oh_share = total_oh / (sites_count * 26) if sites_count * 26 > 0 else 0
                    
                    for date_str in daily_totals:
                        daily_totals[date_str]['oh_share'] = daily_oh_share
                        daily_totals[date_str]['net'] = (
                            daily_totals[date_str]['revenue'] - 
                            daily_totals[date_str]['labour'] - 
                            daily_totals[date_str]['oh_share']
                        )
                    
                    sorted_dates = sorted(daily_totals.keys())
                    cumulative = 0
                    
                    # Get previous month's cumulative
                    prev_month = f"{year}-{str(int(month_num) - 1).zfill(2)}"
                    if int(month_num) > 1:
                        prev_month_start = f"{year}-{str(int(month_num) - 1).zfill(2)}-01"
                        prev_month_end = f"{year}-{str(int(month_num) - 1).zfill(2)}-{calendar.monthrange(int(year), int(month_num)-1)[1]}"
                        prev_tracker = CumulativeTracker.query.filter(
                            CumulativeTracker.date >= dt.strptime(prev_month_start, '%Y-%m-%d'),
                            CumulativeTracker.date <= dt.strptime(prev_month_end, '%Y-%m-%d')
                        ).order_by(CumulativeTracker.date.desc()).first()
                        if prev_tracker:
                            cumulative = prev_tracker.cumulative
                    
                    for date_str in sorted_dates:
                        day_data = daily_totals[date_str]
                        net = day_data['revenue'] - day_data['labour'] - day_data['oh_share']
                        cumulative += net
                        status = '✅ Profit' if cumulative > 0 else '❌ Loss' if cumulative < 0 else '⚖️ Barabar'
                        
                        existing = CumulativeTracker.query.filter_by(date=date_str).first()
                        if existing:
                            existing.revenue = day_data['revenue']
                            existing.labour = day_data['labour']
                            existing.oh_share = day_data['oh_share']
                            existing.net = net
                            existing.cumulative = cumulative
                            existing.status = status
                            existing.notes = day_data['notes']
                        else:
                            tracker = CumulativeTracker(
                                id=generate_id(),
                                date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                                revenue=day_data['revenue'],
                                labour=day_data['labour'],
                                oh_share=day_data['oh_share'],
                                net=net,
                                cumulative=cumulative,
                                status=status,
                                notes=day_data['notes']
                            )
                            db.session.add(tracker)
                    
                    db.session.commit()
                    results.append({
                        'month': month,
                        'status': 'calculated',
                        'count': len(entries),
                        'days': len(sorted_dates)
                    })
                else:
                    results.append({
                        'month': month,
                        'status': 'no entries',
                        'count': 0
                    })
            except Exception as e:
                results.append({
                    'month': month,
                    'status': 'error',
                    'error': str(e)
                })
        
        return jsonify({
            'message': 'Auto-calculation completed',
            'results': results
        }), 200
        
    except Exception as e:
        print(f"Error in auto_calculate_all: {str(e)}")
        return jsonify({'error': str(e)}), 500