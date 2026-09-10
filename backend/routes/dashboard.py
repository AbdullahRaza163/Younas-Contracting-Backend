# routes/dashboard.py
from flask import request, jsonify, send_file
from models import db, Site, Worker, DailyEntry, Attendance
from models.dashboard import DashboardStats
from sqlalchemy import and_, or_
from datetime import datetime
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# Import the blueprint from routes
from routes import dashboard_bp

# ============================================
# DASHBOARD DATA
# ============================================

@dashboard_bp.route('', methods=['GET', 'OPTIONS'])
def get_dashboard_data():
    """Get dashboard data with filters"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'OK'})
    
    try:
        # Get query parameters
        period = request.args.get('period', 'today')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        site_id = request.args.get('site_id', 'all')
        worker_id = request.args.get('worker_id', 'all')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        
        # Get date range
        date_range = DashboardStats.get_date_range(period, start_date, end_date)
        start = date_range['start']
        end = date_range['end']
        
        # Build filters
        entry_filters = [DailyEntry.date >= start, DailyEntry.date <= end]
        attendance_filters = [Attendance.date >= start, Attendance.date <= end]
        
        # Apply site filter
        if site_id and site_id != 'all':
            entry_filters.append(DailyEntry.site_id == site_id)
            attendance_filters.append(Attendance.site_id == site_id)
        
        # Apply worker filter
        if worker_id and worker_id != 'all':
            attendance_filters.append(Attendance.worker_id == worker_id)
        
        # Get data
        entries_query = DailyEntry.query.filter(and_(*entry_filters))
        total_entries_count = entries_query.count()
        entries = entries_query.offset((page - 1) * limit).limit(limit).all()
        
        attendance = Attendance.query.filter(and_(*attendance_filters)).all()
        all_sites = Site.query.filter_by(active=True).all()
        all_workers = Worker.query.all()
        
        # Get all entries for calculations (without pagination)
        all_filtered_entries = DailyEntry.query.filter(and_(*entry_filters)).all()
        
        # Calculate statistics
        stats = DashboardStats.calculate_stats(all_filtered_entries, attendance, all_workers)
        
        # Get site performance
        site_performance = DashboardStats.get_site_performance(all_filtered_entries, all_sites)
        
        # Get expense breakdown
        expense_breakdown = DashboardStats.get_expense_breakdown(all_filtered_entries)
        
        # Get chart data
        chart_data = DashboardStats.get_chart_data(all_filtered_entries)
        
        # Get month comparison
        all_entries_for_comparison = DailyEntry.query.all()
        month_comparison = DashboardStats.get_month_comparison(
            all_entries_for_comparison, 
            site_id, 
            worker_id
        )
        
        # Get selected details
        worker_details = None
        if worker_id and worker_id != 'all':
            worker_details = Worker.query.get(worker_id)
        
        site_details = None
        if site_id and site_id != 'all':
            site_details = Site.query.get(site_id)
        
        return jsonify({
            'success': True,
            'data': {
                'entries': [e.to_dict() for e in entries],
                'attendance': [a.to_dict() for a in attendance],
                'sites': [s.to_dict() for s in all_sites],
                'workers': [w.to_dict() for w in all_workers],
                'stats': stats,
                'sitePerformance': site_performance,
                'expenseBreakdown': expense_breakdown,
                'monthComparison': month_comparison,
                'chartData': chart_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total_entries_count,
                    'pages': (total_entries_count + limit - 1) // limit
                },
                'selectedWorkerDetails': worker_details.to_dict() if worker_details else None,
                'selectedSiteDetails': site_details.to_dict() if site_details else None
            }
        }), 200
        
    except Exception as e:
        print(f"Error in get_dashboard_data: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error fetching dashboard data',
            'error': str(e)
        }), 500


@dashboard_bp.route('/filters', methods=['GET', 'OPTIONS'])
def get_filter_options():
    """Get available sites and workers for filters"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'OK'})
    
    try:
        sites = Site.query.filter_by(active=True).all()
        workers = Worker.query.all()
        
        return jsonify({
            'success': True,
            'data': {
                'sites': [{'id': s.id, 'name': s.name} for s in sites],
                'workers': [{'id': w.id, 'name': w.name} for w in workers]
            }
        }), 200
        
    except Exception as e:
        print(f"Error in get_filter_options: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error fetching filter options',
            'error': str(e)
        }), 500


@dashboard_bp.route('/export', methods=['GET', 'OPTIONS'])
def export_dashboard_report():
    """Export dashboard report as Excel file"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'OK'})
    
    try:
        # Get query parameters
        period = request.args.get('period', 'today')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        site_id = request.args.get('site_id', 'all')
        
        # Get date range
        date_range = DashboardStats.get_date_range(period, start_date, end_date)
        start = date_range['start']
        end = date_range['end']
        
        # Build filters
        entry_filters = [DailyEntry.date >= start, DailyEntry.date <= end]
        
        if site_id and site_id != 'all':
            entry_filters.append(DailyEntry.site_id == site_id)
        
        entries = DailyEntry.query.filter(and_(*entry_filters)).all()
        all_sites = Site.query.filter_by(active=True).all()
        
        # Create workbook
        wb = Workbook()
        wb.remove(wb.active)
        
        # === SUMMARY SHEET ===
        ws_summary = wb.create_sheet("Summary")
        
        headers = ['Metric', 'Amount (BD)']
        for col, header in enumerate(headers, 1):
            cell = ws_summary.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, size=12)
            cell.fill = PatternFill(start_color="009846", end_color="009846", fill_type="solid")
            cell.font = Font(bold=True, size=12, color="FFFFFF")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        total_revenue = sum(e.kamai or 0 for e in entries)
        total_labour = sum(e.labour or 0 for e in entries)
        total_overhead = sum(e.overhead or 0 for e in entries)
        total_one_time = sum(e.one_time or 0 for e in entries)
        total_profit = total_revenue - total_labour - total_overhead - total_one_time
        
        summary_data = [
            ('Total Revenue', total_revenue),
            ('Total Labour', total_labour),
            ('Total Overhead', total_overhead),
            ('Total One-Time', total_one_time),
            ('Net Profit', total_profit),
            ('Total Entries', len(entries))
        ]
        
        for row_idx, (metric, value) in enumerate(summary_data, 2):
            ws_summary.cell(row=row_idx, column=1, value=metric)
            ws_summary.cell(row=row_idx, column=2, value=value)
            
            if metric == 'Net Profit':
                cell = ws_summary.cell(row=row_idx, column=2)
                if value >= 0:
                    cell.font = Font(color="009846", bold=True)
                else:
                    cell.font = Font(color="dc2626", bold=True)
        
        for col in range(1, 3):
            ws_summary.column_dimensions[get_column_letter(col)].width = 20
        
        # === SITES SHEET ===
        ws_sites = wb.create_sheet("Sites")
        
        site_headers = ['Site', 'Revenue', 'Labour', 'Overhead', 'One-Time', 'Profit', 'Entries']
        for col, header in enumerate(site_headers, 1):
            cell = ws_sites.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, size=12, color="FFFFFF")
            cell.fill = PatternFill(start_color="009846", end_color="009846", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        for row_idx, site in enumerate(all_sites, 2):
            site_entries = [e for e in entries if e.site_id == site.id]
            revenue = sum(e.kamai or 0 for e in site_entries)
            labour = sum(e.labour or 0 for e in site_entries)
            overhead = sum(e.overhead or 0 for e in site_entries)
            one_time = sum(e.one_time or 0 for e in site_entries)
            profit = revenue - labour - overhead - one_time
            
            ws_sites.cell(row=row_idx, column=1, value=site.name)
            ws_sites.cell(row=row_idx, column=2, value=revenue)
            ws_sites.cell(row=row_idx, column=3, value=labour)
            ws_sites.cell(row=row_idx, column=4, value=overhead)
            ws_sites.cell(row=row_idx, column=5, value=one_time)
            ws_sites.cell(row=row_idx, column=6, value=profit)
            ws_sites.cell(row=row_idx, column=7, value=len(site_entries))
            
            profit_cell = ws_sites.cell(row=row_idx, column=6)
            if profit >= 0:
                profit_cell.font = Font(color="009846", bold=True)
            else:
                profit_cell.font = Font(color="dc2626", bold=True)
        
        for col in range(1, 8):
            ws_sites.column_dimensions[get_column_letter(col)].width = 18
        
        # === DAILY SHEET ===
        ws_daily = wb.create_sheet("Daily")
        
        daily_headers = ['Date', 'Revenue', 'Labour', 'Overhead', 'Profit']
        for col, header in enumerate(daily_headers, 1):
            cell = ws_daily.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, size=12, color="FFFFFF")
            cell.fill = PatternFill(start_color="009846", end_color="009846", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        daily_data = {}
        for entry in entries:
            if entry.date not in daily_data:
                daily_data[entry.date] = {
                    'date': entry.date,
                    'revenue': 0,
                    'labour': 0,
                    'overhead': 0,
                    'profit': 0
                }
            daily_data[entry.date]['revenue'] += entry.kamai or 0
            daily_data[entry.date]['labour'] += entry.labour or 0
            daily_data[entry.date]['overhead'] += entry.overhead or 0
            daily_data[entry.date]['profit'] += (entry.kamai or 0) - (entry.labour or 0) - (entry.overhead or 0)
        
        sorted_daily = sorted(daily_data.values(), key=lambda x: x['date'])
        
        for row_idx, day in enumerate(sorted_daily, 2):
            ws_daily.cell(row=row_idx, column=1, value=day['date'])
            ws_daily.cell(row=row_idx, column=2, value=day['revenue'])
            ws_daily.cell(row=row_idx, column=3, value=day['labour'])
            ws_daily.cell(row=row_idx, column=4, value=day['overhead'])
            ws_daily.cell(row=row_idx, column=5, value=day['profit'])
            
            profit_cell = ws_daily.cell(row=row_idx, column=5)
            if day['profit'] >= 0:
                profit_cell.font = Font(color="009846", bold=True)
            else:
                profit_cell.font = Font(color="dc2626", bold=True)
        
        for col in range(1, 6):
            ws_daily.column_dimensions[get_column_letter(col)].width = 18
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        return send_file(
            output,
            as_attachment=True,
            download_name=f'dashboard_report_{start}_to_{end}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"Error in export_dashboard_report: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error exporting report',
            'error': str(e)
        }), 500