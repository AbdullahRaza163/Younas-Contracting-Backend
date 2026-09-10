# models/dashboard.py
from models import db
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_

class DashboardStats:
    """Dashboard statistics helper class"""
    
    @staticmethod
    def get_date_range(period, start_date=None, end_date=None):
        """Get date range based on period"""
        today = datetime.now().date()
        
        if period == 'custom' and start_date and end_date:
            return {'start': start_date, 'end': end_date}
        
        if period == 'today':
            return {'start': today.isoformat(), 'end': today.isoformat()}
        elif period == 'yesterday':
            yesterday = today - timedelta(days=1)
            return {'start': yesterday.isoformat(), 'end': yesterday.isoformat()}
        elif period == 'week':
            start = today - timedelta(days=7)
            return {'start': start.isoformat(), 'end': today.isoformat()}
        elif period == 'month':
            start = today.replace(day=1)
            return {'start': start.isoformat(), 'end': today.isoformat()}
        elif period == 'lastMonth':
            start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            end = today.replace(day=1) - timedelta(days=1)
            return {'start': start.isoformat(), 'end': end.isoformat()}
        elif period == 'year':
            start = today.replace(month=1, day=1)
            return {'start': start.isoformat(), 'end': today.isoformat()}
        elif period == 'lastYear':
            start = today.replace(year=today.year - 1, month=1, day=1)
            end = today.replace(year=today.year - 1, month=12, day=31)
            return {'start': start.isoformat(), 'end': end.isoformat()}
        else:
            return {'start': today.isoformat(), 'end': today.isoformat()}

    @staticmethod
    def calculate_stats(entries, attendance, workers):
        """Calculate dashboard statistics"""
        total_revenue = sum(e.kamai or 0 for e in entries)
        total_labour = sum(e.labour or 0 for e in entries)
        total_overhead = sum(e.overhead or 0 for e in entries)
        total_one_time = sum(e.one_time or 0 for e in entries)
        total_profit = total_revenue - total_labour - total_overhead - total_one_time
        
        workers_present = sum(1 for a in attendance if a.present)
        
        total_hours = 0
        for a in attendance:
            if a.checked_in and a.checked_out:
                total_hours += DashboardStats.calculate_hours_worked(a.checked_in, a.checked_out)
        
        # Calculate total wages
        total_wages = 0
        for worker in workers:
            worker_attendance = [a for a in attendance if a.worker_id == worker.id]
            worker_hours = 0
            for a in worker_attendance:
                if a.checked_in and a.checked_out:
                    worker_hours += DashboardStats.calculate_hours_worked(a.checked_in, a.checked_out)
            total_wages += worker_hours * (worker.daily_rate or 0)
        
        return {
            'totalRevenue': total_revenue,
            'totalLabour': total_labour,
            'totalOverhead': total_overhead,
            'totalOneTime': total_one_time,
            'totalProfit': total_profit,
            'totalWorkers': len(workers),
            'workersPresent': workers_present,
            'totalHours': round(total_hours, 2),
            'totalWages': total_wages,
            'entryCount': len(entries),
            'attendanceCount': len(attendance),
            'isProfit': total_profit >= 0
        }

    @staticmethod
    def calculate_hours_worked(checked_in, checked_out):
        """Calculate hours worked between check-in and check-out"""
        if not checked_in or not checked_out:
            return 0
        delta = checked_out - checked_in
        return delta.total_seconds() / 3600

    @staticmethod
    def get_site_performance(entries, sites):
        """Calculate site performance"""
        site_performance = []
        
        for site in sites:
            site_entries = [e for e in entries if e.site_id == site.id]
            revenue = sum(e.kamai or 0 for e in site_entries)
            labour = sum(e.labour or 0 for e in site_entries)
            overhead = sum(e.overhead or 0 for e in site_entries)
            one_time = sum(e.one_time or 0 for e in site_entries)
            profit = revenue - labour - overhead - one_time
            
            site_performance.append({
                'id': site.id,
                'name': site.name,
                'revenue': revenue,
                'labour': labour,
                'overhead': overhead,
                'oneTime': one_time,
                'profit': profit,
                'entryCount': len(site_entries),
                'profitMargin': (profit / revenue * 100) if revenue > 0 else 0
            })
        
        site_performance.sort(key=lambda x: x['profit'], reverse=True)
        return site_performance

    @staticmethod
    def get_expense_breakdown(entries):
        """Get expense breakdown for pie chart"""
        total_labour = sum(e.labour or 0 for e in entries)
        total_overhead = sum(e.overhead or 0 for e in entries)
        total_one_time = sum(e.one_time or 0 for e in entries)
        
        breakdown = []
        if total_labour > 0:
            breakdown.append({'name': 'Labour', 'value': total_labour})
        if total_overhead > 0:
            breakdown.append({'name': 'Overhead', 'value': total_overhead})
        if total_one_time > 0:
            breakdown.append({'name': 'One-Time', 'value': total_one_time})
        
        return breakdown

    @staticmethod
    def get_chart_data(entries):
        """Get daily chart data"""
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
        
        chart_data = sorted(daily_data.values(), key=lambda x: x['date'])
        return chart_data

    @staticmethod
    def get_month_comparison(entries_all, site_id=None, worker_id=None):
        """Get month-over-month comparison"""
        today = datetime.now().date()
        current_month = today.month
        current_year = today.year
        
        def get_month_data(month, year):
            month_entries = [e for e in entries_all if 
                           datetime.strptime(e.date, '%Y-%m-%d').month == month and
                           datetime.strptime(e.date, '%Y-%m-%d').year == year]
            
            if site_id and site_id != 'all':
                month_entries = [e for e in month_entries if e.site_id == site_id]
            
            revenue = sum(e.kamai or 0 for e in month_entries)
            expenses = sum(e.labour or 0 for e in month_entries) + \
                      sum(e.overhead or 0 for e in month_entries) + \
                      sum(e.one_time or 0 for e in month_entries)
            
            return {
                'revenue': revenue,
                'expenses': expenses,
                'profit': revenue - expenses,
                'count': len(month_entries)
            }
        
        current = get_month_data(current_month, current_year)
        
        prev_month = current_month - 1
        prev_year = current_year
        if prev_month == 0:
            prev_month = 12
            prev_year = current_year - 1
        
        previous = get_month_data(prev_month, prev_year)
        
        profit_change = ((current['profit'] - previous['profit']) / abs(previous['profit']) * 100) if previous['profit'] != 0 else 0
        
        return {
            'current': current,
            'previous': previous,
            'profitChange': round(profit_change, 2),
            'isUp': current['profit'] >= previous['profit']
        }