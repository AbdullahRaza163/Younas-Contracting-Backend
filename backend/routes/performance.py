# routes/performance.py
from flask import request, jsonify
from models import db, Project, Entry, Site, Worker, WorkerTeam, TeamMember, Attendance, Inspection, SafetyIncident, Issue
from routes import performance_bp
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
import json

@performance_bp.route('/metrics', methods=['GET'])
def get_performance_metrics():
    """Get performance metrics with filters - Dynamic from database"""
    try:
        period = request.args.get('period', 'monthly')
        site_id = request.args.get('siteId')
        team_id = request.args.get('teamId')
        worker_id = request.args.get('workerId')
        start_date = request.args.get('startDate')
        end_date = request.args.get('endDate')
        
        # Calculate date range
        if not start_date or not end_date:
            end_date = datetime.now().date()
            if period == 'daily':
                start_date = end_date - timedelta(days=1)
            elif period == 'weekly':
                start_date = end_date - timedelta(days=7)
            elif period == 'monthly':
                start_date = end_date - timedelta(days=30)
            elif period == 'quarterly':
                start_date = end_date - timedelta(days=90)
            else:  # yearly
                start_date = end_date - timedelta(days=365)
        
        # Build query filters for entries
        entry_filters = [
            Entry.date >= start_date,
            Entry.date <= end_date
        ]
        
        if site_id:
            entry_filters.append(Entry.site_id == site_id)
        if worker_id:
            # Since worker_id doesn't exist in entries, filter by site
            # Get worker's site from team membership
            worker = Worker.query.get(worker_id)
            if worker:
                # Try to find worker's site through team
                team_member = TeamMember.query.filter_by(worker_id=worker_id).first()
                if team_member:
                    team = WorkerTeam.query.get(team_member.team_id)
                    if team and team.site_id:
                        entry_filters.append(Entry.site_id == team.site_id)
        if team_id:
            team = WorkerTeam.query.get(team_id)
            if team and team.site_id:
                entry_filters.append(Entry.site_id == team.site_id)
        
        # Get entries
        entries = Entry.query.filter(and_(*entry_filters)).all()
        
        # 1. Productivity Metrics
        total_entries = len(entries)
        total_revenue = sum(e.kamai or 0 for e in entries)
        total_labour = sum(e.labour or 0 for e in entries)
        
        # Get active workers count
        active_workers = Worker.query.filter_by(active=True).count() or 1
        
        # 2. Financial Metrics
        total_cost = sum(
            (e.labour or 0) + (e.material_cost or 0) + (e.equipment_cost or 0) + 
            (e.transport_cost or 0) + (e.other_expense or 0) 
            for e in entries
        )
        total_profit = total_revenue - total_cost
        
        # Get project count
        projects = Project.query.all()
        
        # 3. Quality Metrics (from inspections)
        inspection_filters = [
            Inspection.inspection_date >= start_date,
            Inspection.inspection_date <= end_date
        ]
        if site_id:
            inspection_filters.append(Inspection.site_id == site_id)
        inspections = Inspection.query.filter(and_(*inspection_filters)).all()
        
        total_inspections = len(inspections)
        passed = sum(1 for i in inspections if i.status in ['approved', 'completed'])
        failed = sum(1 for i in inspections if i.status == 'rejected')
        avg_score = sum(i.score or 0 for i in inspections) / total_inspections if total_inspections > 0 else 0
        
        # 4. Safety Metrics (from incidents)
        incident_filters = [
            SafetyIncident.incident_date >= start_date,
            SafetyIncident.incident_date <= end_date
        ]
        if site_id:
            incident_filters.append(SafetyIncident.site_id == site_id)
        incidents = SafetyIncident.query.filter(and_(*incident_filters)).all()
        
        total_incidents = len(incidents)
        resolved = sum(1 for i in incidents if i.status in ['resolved', 'closed'])
        critical_incidents = sum(1 for i in incidents if i.severity == 'critical')
        high_incidents = sum(1 for i in incidents if i.severity == 'high')
        
        # 5. Issue Metrics
        issue_filters = []
        if site_id:
            issue_filters.append(Issue.site_id == site_id)
        issues = Issue.query.filter(and_(*issue_filters)).all() if issue_filters else Issue.query.all()
        open_issues = sum(1 for i in issues if i.status == 'open')
        critical_issues = sum(1 for i in issues if i.severity == 'critical')
        
        metrics = {
            'period': period,
            'startDate': start_date.isoformat() if start_date else None,
            'endDate': end_date.isoformat() if end_date else None,
            'productivity': {
                'totalEntries': total_entries,
                'avgDailyEntries': round(total_entries / max((end_date - start_date).days, 1), 1),
                'totalRevenue': round(total_revenue, 3),
                'avgRevenuePerEntry': round(total_revenue / max(total_entries, 1), 3),
                'labourCost': round(total_labour, 3),
                'labourToRevenueRatio': round((total_labour / max(total_revenue, 1)) * 100, 1),
                'activeWorkers': active_workers,
                'projectsCount': len(projects)
            },
            'financial': {
                'totalRevenue': round(total_revenue, 3),
                'totalCost': round(total_cost, 3),
                'totalProfit': round(total_profit, 3),
                'profitMargin': round((total_profit / max(total_revenue, 1)) * 100, 1),
                'avgProfitPerEntry': round(total_profit / max(total_entries, 1), 3)
            },
            'quality': {
                'totalInspections': total_inspections,
                'passed': passed,
                'failed': failed,
                'passRate': round((passed / max(total_inspections, 1)) * 100, 1),
                'avgScore': round(avg_score, 1)
            },
            'safety': {
                'totalIncidents': total_incidents,
                'resolved': resolved,
                'resolutionRate': round((resolved / max(total_incidents, 1)) * 100, 1),
                'criticalIncidents': critical_incidents,
                'highIncidents': high_incidents,
                'openIssues': open_issues,
                'criticalIssues': critical_issues
            }
        }
        
        return jsonify(metrics)
    except Exception as e:
        print(f"Error in get_performance_metrics: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/rankings', methods=['GET'])
def get_performance_rankings():
    """Get performance rankings dynamically from database"""
    try:
        entity_type = request.args.get('entityType', 'site')
        period = request.args.get('period', 'monthly')
        limit = int(request.args.get('limit', 10))
        
        end_date = datetime.now().date()
        if period == 'daily':
            start_date = end_date - timedelta(days=1)
        elif period == 'weekly':
            start_date = end_date - timedelta(days=7)
        elif period == 'monthly':
            start_date = end_date - timedelta(days=30)
        elif period == 'quarterly':
            start_date = end_date - timedelta(days=90)
        else:  # yearly
            start_date = end_date - timedelta(days=365)
        
        rankings = []
        
        if entity_type == 'site':
            sites = Site.query.filter_by(active=True).all()
            for site in sites:
                entries = Entry.query.filter(
                    Entry.site_id == site.id,
                    Entry.date >= start_date,
                    Entry.date <= end_date
                ).all()
                
                total_revenue = sum(e.kamai or 0 for e in entries)
                total_cost = sum(
                    (e.labour or 0) + (e.material_cost or 0) + (e.equipment_cost or 0) + 
                    (e.transport_cost or 0) + (e.other_expense or 0)
                    for e in entries
                )
                profit = total_revenue - total_cost
                profit_margin = (profit / max(total_revenue, 1)) * 100 if total_revenue > 0 else 0
                
                rankings.append({
                    'id': site.id,
                    'name': site.name or 'Unknown Site',
                    'score': round(profit_margin, 1),
                    'revenue': round(total_revenue, 3),
                    'profit': round(profit, 3),
                    'entries': len(entries)
                })
        
        elif entity_type == 'team':
            teams = WorkerTeam.query.all()
            for team in teams:
                members = TeamMember.query.filter_by(team_id=team.id).all()
                
                # Get entries using site_id
                entries = []
                if team.site_id:
                    entries = Entry.query.filter(
                        Entry.site_id == team.site_id,
                        Entry.date >= start_date,
                        Entry.date <= end_date
                    ).all()
                
                total_revenue = sum(e.kamai or 0 for e in entries)
                total_cost = sum(
                    (e.labour or 0) + (e.material_cost or 0) + (e.equipment_cost or 0) + 
                    (e.transport_cost or 0) + (e.other_expense or 0)
                    for e in entries
                )
                profit = total_revenue - total_cost
                profit_margin = (profit / max(total_revenue, 1)) * 100 if total_revenue > 0 else 0
                
                # Calculate average revenue per member
                avg_revenue_per_member = total_revenue / max(len(members), 1)
                
                rankings.append({
                    'id': team.id,
                    'name': team.name or 'Unknown Team',
                    'score': round(profit_margin, 1) if total_revenue > 0 else 0,
                    'revenue': round(total_revenue, 3),
                    'profit': round(profit, 3),
                    'entries': len(entries),
                    'members': len(members),
                    'avgRevenuePerMember': round(avg_revenue_per_member, 3)
                })
        
        elif entity_type == 'worker':
            workers = Worker.query.filter_by(active=True).all()
            for worker in workers:
                # Try to find entries for this worker through team
                entries = []
                team_member = TeamMember.query.filter_by(worker_id=worker.id).first()
                if team_member:
                    team = WorkerTeam.query.get(team_member.team_id)
                    if team and team.site_id:
                        entries = Entry.query.filter(
                            Entry.site_id == team.site_id,
                            Entry.date >= start_date,
                            Entry.date <= end_date
                        ).all()
                
                total_revenue = sum(e.kamai or 0 for e in entries)
                total_labour = sum(e.labour or 0 for e in entries)
                
                # Get attendance
                attendances = Attendance.query.filter(
                    Attendance.worker_id == worker.id,
                    Attendance.date >= start_date,
                    Attendance.date <= end_date,
                    Attendance.present == True
                ).all()
                days_present = len(attendances)
                
                # Calculate productivity (revenue per day)
                productivity = total_revenue / max(days_present, 1) if days_present > 0 else 0
                
                rankings.append({
                    'id': worker.id,
                    'name': worker.name or 'Unknown Worker',
                    'score': round(total_revenue, 1),
                    'revenue': round(total_revenue, 3),
                    'labour': round(total_labour, 3),
                    'entries': len(entries),
                    'daysPresent': days_present,
                    'productivity': round(productivity, 3)
                })
        
        # Sort by score descending and limit
        rankings.sort(key=lambda x: x['score'], reverse=True)
        for i, item in enumerate(rankings[:limit]):
            item['rank'] = i + 1
        
        return jsonify(rankings[:limit])
    except Exception as e:
        print(f"Error in get_performance_rankings: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify([])

@performance_bp.route('/trends', methods=['GET'])
def get_performance_trends():
    """Get performance trends from database"""
    try:
        metric = request.args.get('metric', 'revenue')
        entity_type = request.args.get('entityType', 'site')
        entity_id = request.args.get('entityId')
        months = int(request.args.get('months', 12))
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=months * 30)
        
        trends = []
        current = start_date.replace(day=1)
        
        while current <= end_date:
            # Calculate month end
            if current.month == 12:
                month_end = current.replace(year=current.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = current.replace(month=current.month + 1, day=1) - timedelta(days=1)
            
            # Build query
            entry_filters = [
                Entry.date >= current,
                Entry.date <= month_end
            ]
            
            if entity_type == 'site' and entity_id:
                entry_filters.append(Entry.site_id == entity_id)
            elif entity_type == 'team' and entity_id:
                team = WorkerTeam.query.get(entity_id)
                if team and team.site_id:
                    entry_filters.append(Entry.site_id == team.site_id)
            elif entity_type == 'worker' and entity_id:
                team_member = TeamMember.query.filter_by(worker_id=entity_id).first()
                if team_member:
                    team = WorkerTeam.query.get(team_member.team_id)
                    if team and team.site_id:
                        entry_filters.append(Entry.site_id == team.site_id)
            
            entries = Entry.query.filter(and_(*entry_filters)).all()
            
            if metric == 'revenue':
                value = sum(e.kamai or 0 for e in entries)
            elif metric == 'profit':
                value = sum(
                    (e.kamai or 0) - (e.labour or 0) - (e.material_cost or 0) - 
                    (e.equipment_cost or 0) - (e.transport_cost or 0) - (e.other_expense or 0)
                    for e in entries
                )
            elif metric == 'entries':
                value = len(entries)
            else:
                value = sum(e.kamai or 0 for e in entries)
            
            trends.append({
                'period': current.strftime('%b %Y'),
                'value': round(value, 3),
                'date': current.isoformat()
            })
            
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)
        
        return jsonify(trends)
    except Exception as e:
        print(f"Error in get_performance_trends: {str(e)}")
        return jsonify({'error': str(e)}), 500

@performance_bp.route('/kpis', methods=['GET'])
def get_kpis():
    """Get KPI definitions and current values from database"""
    try:
        today = datetime.now().date()
        month_start = today.replace(day=1)
        
        # 1. Revenue Per Worker
        workers = Worker.query.filter_by(active=True).count() or 1
        entries = Entry.query.filter(Entry.date >= month_start, Entry.date <= today).all()
        total_revenue = sum(e.kamai or 0 for e in entries)
        revenue_per_worker = round(total_revenue / workers, 3)
        
        # 2. Profit Margin
        total_cost = sum(
            (e.labour or 0) + (e.material_cost or 0) + (e.equipment_cost or 0) + 
            (e.transport_cost or 0) + (e.other_expense or 0)
            for e in entries
        )
        profit = total_revenue - total_cost
        profit_margin = round((profit / max(total_revenue, 1)) * 100, 1)
        
        # 3. Safety Incident Rate
        incidents = SafetyIncident.query.filter(
            SafetyIncident.incident_date >= month_start,
            SafetyIncident.incident_date <= today
        ).count()
        
        total_hours = 0
        for e in entries:
            if hasattr(e, 'total_hours') and e.total_hours:
                total_hours += e.total_hours
            else:
                total_hours += 8
        incident_rate = round((incidents / max(total_hours, 1)) * 1000, 2)
        
        # 4. Quality Pass Rate
        inspections = Inspection.query.filter(
            Inspection.inspection_date >= month_start,
            Inspection.inspection_date <= today
        ).all()
        passed = sum(1 for i in inspections if i.status in ['approved', 'completed'])
        pass_rate = round((passed / max(len(inspections), 1)) * 100, 1)
        
        # 5. Project Completion Rate
        projects = Project.query.all()
        completed = sum(1 for p in projects if p.status == 'completed')
        completion_rate = round((completed / max(len(projects), 1)) * 100, 1)
        
        kpis = [
            {'id': 'kpi_001', 'name': 'Revenue Per Worker', 'category': 'productivity', 
             'value': revenue_per_worker, 'target': 5000, 'unit': 'BD'},
            {'id': 'kpi_002', 'name': 'Profit Margin', 'category': 'financial', 
             'value': profit_margin, 'target': 25, 'unit': '%'},
            {'id': 'kpi_003', 'name': 'Safety Incident Rate', 'category': 'safety', 
             'value': incident_rate, 'target': 0, 'unit': 'per 1000 hours'},
            {'id': 'kpi_004', 'name': 'Quality Pass Rate', 'category': 'quality', 
             'value': pass_rate, 'target': 95, 'unit': '%'},
            {'id': 'kpi_005', 'name': 'Project Completion Rate', 'category': 'productivity', 
             'value': completion_rate, 'target': 90, 'unit': '%'}
        ]
        
        return jsonify(kpis)
    except Exception as e:
        print(f"Error in get_kpis: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify([])