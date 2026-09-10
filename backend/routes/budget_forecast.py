# routes/budget_forecast.py - Updated to use site_id as fallback
from flask import request, jsonify
from models import db, Budget, BudgetCategory, Forecast, CashFlow, BudgetAlert, WhatIfScenario, Project, Entry
from utils.helpers import generate_id
from routes import budget_bp
from datetime import datetime, timedelta
import calendar
import random
import string

@budget_bp.route('/summary', methods=['GET'])
def get_budget_summary():
    """Get comprehensive budget summary"""
    try:
        project_id = request.args.get('projectId')
        year = request.args.get('year', str(datetime.now().year))
        
        # Get all budgets for the year
        query = Budget.query.filter_by(year=int(year))
        if project_id:
            query = query.filter_by(project_id=project_id)
        budgets = query.all()
        
        # Get all projects
        projects = Project.query.all() if not project_id else Project.query.filter_by(id=project_id).all()
        
        summary = {
            'year': year,
            'totalBudget': sum(b.amount for b in budgets) if budgets else sum(p.budget or 0 for p in projects),
            'totalActual': 0,
            'totalVariance': 0,
            'projects': []
        }
        
        total_actual = 0
        total_revenue = 0
        
        for project in projects:
            project_budgets = [b for b in budgets if b.project_id == project.id]
            
            # Try to get entries by project_id first, then fallback to site_id
            project_entries = Entry.query.filter_by(project_id=project.id).all()
            if not project_entries and project.site_id:
                project_entries = Entry.query.filter_by(site_id=project.site_id).all()
            
            revenue = sum(e.kamai or 0 for e in project_entries)
            cost = sum(
                (e.labour or 0) + (e.material_cost or 0) + (e.equipment_cost or 0) + 
                (e.transport_cost or 0) + (e.other_expense or 0)
                for e in project_entries
            )
            
            total_actual += cost
            total_revenue += revenue
            
            project_budget = sum(b.amount for b in project_budgets) or project.budget or 0
            
            summary['projects'].append({
                'projectId': project.id,
                'projectName': project.name,
                'budget': project_budget,
                'actualCost': cost,
                'revenue': revenue,
                'profit': revenue - cost,
                'variance': project_budget - cost,
                'progress': (cost / project_budget * 100) if project_budget > 0 else 0,
                'entriesCount': len(project_entries),
                'status': project.status,
                'health': 'over_budget' if cost > project_budget else 'on_track' if cost < project_budget * 0.75 else 'warning'
            })
        
        summary['totalActual'] = total_actual
        summary['totalRevenue'] = total_revenue
        summary['totalProfit'] = total_revenue - total_actual
        summary['totalVariance'] = summary['totalBudget'] - total_actual
        
        return jsonify(summary)
    except Exception as e:
        print(f"Error in get_budget_summary: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@budget_bp.route('/budgets', methods=['GET'])
def get_budgets():
    """Get budgets with filters"""
    try:
        project_id = request.args.get('projectId')
        month = request.args.get('month')
        category = request.args.get('category')
        
        query = Budget.query
        if project_id:
            query = query.filter_by(project_id=project_id)
        if month:
            query = query.filter_by(month=month)
        if category:
            query = query.filter_by(category=category)
        
        budgets = query.order_by(Budget.month.desc()).all()
        
        # If no budgets exist, create default budgets from projects
        if not budgets and not project_id:
            projects = Project.query.all()
            for project in projects:
                if project.budget and project.budget > 0:
                    default_budget = Budget(
                        id=generate_id(),
                        project_id=project.id,
                        category='general',
                        amount=project.budget,
                        actual_amount=0,
                        month=datetime.now().strftime('%Y-%m'),
                        year=datetime.now().year,
                        status='active',
                        notes='Auto-generated from project budget'
                    )
                    db.session.add(default_budget)
            db.session.commit()
            budgets = Budget.query.all()
        
        return jsonify([b.to_dict() for b in budgets])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@budget_bp.route('/budgets/update-all', methods=['POST'])
def update_all_budgets():
    """Update all budgets with actual amounts from entries"""
    try:
        projects = Project.query.all()
        updated = 0
        
        for project in projects:
            # Get entries by project_id or site_id
            entries = Entry.query.filter_by(project_id=project.id).all()
            if not entries and project.site_id:
                entries = Entry.query.filter_by(site_id=project.site_id).all()
            
            if not entries:
                continue
            
            # Calculate actual costs
            actual_cost = sum(
                (e.labour or 0) + (e.material_cost or 0) + (e.equipment_cost或0) + 
                (e.transport_cost or 0) + (e.other_expense or 0)
                for e in entries
            )
            
            # Find or create budget
            budget = Budget.query.filter_by(project_id=project.id).first()
            if not budget:
                budget = Budget(
                    id=generate_id(),
                    project_id=project.id,
                    category='general',
                    amount=project.budget or 0,
                    month=datetime.now().strftime('%Y-%m'),
                    year=datetime.now().year,
                    status='active'
                )
                db.session.add(budget)
            
            budget.actual_amount = actual_cost
            budget.calculate_variance()
            updated += 1
        
        db.session.commit()
        return jsonify({'message': f'Updated {updated} budgets'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/forecasts/generate', methods=['POST'])
def generate_forecast():
    """Generate forecast based on historical data"""
    try:
        data = request.json
        project_id = data.get('projectId')
        months = int(data.get('months', 6))
        
        # Get project
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Get entries by project_id or site_id
        entries = Entry.query.filter_by(project_id=project_id).order_by(Entry.date.desc()).limit(30).all()
        if not entries and project.site_id:
            entries = Entry.query.filter_by(site_id=project.site_id).order_by(Entry.date.desc()).limit(30).all()
        
        if len(entries) < 3:
            return jsonify({'error': 'Insufficient data for forecasting (need at least 3 entries)'}), 400
        
        # Calculate averages
        total_revenue = sum(e.kamai or 0 for e in entries)
        total_cost = sum(
            (e.labour or 0) + (e.material_cost or 0) + (e.equipment_cost or 0) + 
            (e.transport_cost or 0) + (e.other_expense or 0)
            for e in entries
        )
        avg_revenue = total_revenue / len(entries)
        avg_cost = total_cost / len(entries)
        
        # Calculate growth rate
        if len(entries) >= 6:
            recent = entries[:3]
            older = entries[-3:]
            recent_revenue = sum(e.kamai or 0 for e in recent) / len(recent) if recent else 0
            older_revenue = sum(e.kamai or 0 for e in older) / len(older) if older else 0
            growth_rate = ((recent_revenue - older_revenue) / older_revenue * 100) if older_revenue > 0 else 0
        else:
            growth_rate = 0
        
        # Generate forecasts
        forecasts = []
        now = datetime.now()
        for i in range(1, months + 1):
            # Calculate month
            month = now.month + i
            year = now.year
            while month > 12:
                month -= 12
                year += 1
            month_key = f"{year}-{str(month).zfill(2)}"
            
            predicted_revenue = avg_revenue * (1 + (growth_rate / 100) * i)
            predicted_cost = avg_cost * (1 + (growth_rate / 100) * i)
            predicted_profit = predicted_revenue - predicted_cost
            
            # Check if forecast already exists
            existing = Forecast.query.filter_by(project_id=project_id, month=month_key).first()
            if existing:
                existing.predicted_revenue = predicted_revenue
                existing.predicted_cost = predicted_cost
                existing.predicted_profit = predicted_profit
                existing.confidence_score = max(0, 100 - (i * 5))
                forecasts.append(existing)
            else:
                forecast = Forecast(
                    id=generate_id(),
                    project_id=project_id,
                    month=month_key,
                    predicted_revenue=predicted_revenue,
                    predicted_cost=predicted_cost,
                    predicted_profit=predicted_profit,
                    confidence_score=max(0, 100 - (i * 5))
                )
                db.session.add(forecast)
                forecasts.append(forecast)
        
        db.session.commit()
        return jsonify([f.to_dict() for f in forecasts]), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in generate_forecast: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/cashflow/generate', methods=['POST'])
def generate_cash_flow():
    """Generate cash flow from entries"""
    try:
        data = request.json
        project_id = data.get('projectId')
        
        # Get project
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        # Get entries by project_id or site_id
        entries = Entry.query.filter_by(project_id=project_id).order_by(Entry.date).all()
        if not entries and project.site_id:
            entries = Entry.query.filter_by(site_id=project.site_id).order_by(Entry.date).all()
        
        if not entries:
            return jsonify({'error': 'No entries found for this project'}), 400
        
        # Clear existing cash flows
        CashFlow.query.filter_by(project_id=project_id).delete()
        
        # Generate cash flows from entries
        cumulative = 0
        for entry in entries:
            inflow = entry.kamai or 0
            outflow = (entry.labour or 0) + (entry.material_cost or 0) + (entry.equipment_cost or 0) + \
                      (entry.transport_cost or 0) + (entry.other_expense or 0)
            net_flow = inflow - outflow
            cumulative += net_flow
            
            cash_flow = CashFlow(
                id=generate_id(),
                project_id=project_id,
                date=entry.date,
                inflow=inflow,
                outflow=outflow,
                net_flow=net_flow,
                cumulative_balance=cumulative,
                type='operational',
                description=entry.note or 'From entry'
            )
            db.session.add(cash_flow)
        
        db.session.commit()
        return jsonify({'message': f'Generated {len(entries)} cash flow records', 'total': len(entries)}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in generate_cash_flow: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/update-all', methods=['POST'])
def update_all_project_data():
    """Update all project budget data from entries"""
    try:
        projects = Project.query.all()
        results = []
        
        for project in projects:
            # Get entries by project_id or site_id
            entries = Entry.query.filter_by(project_id=project.id).all()
            if not entries and project.site_id:
                entries = Entry.query.filter_by(site_id=project.site_id).all()
            
            if not entries:
                results.append({
                    'project': project.name,
                    'status': 'no_entries',
                    'message': 'No entries found'
                })
                continue
            
            # Calculate totals
            total_revenue = sum(e.kamai or 0 for e in entries)
            total_cost = sum(
                (e.labour or 0) + (e.material_cost or 0) + (e.equipment_cost or 0) + 
                (e.transport_cost or 0) + (e.other_expense or 0)
                for e in entries
            )
            
            # Update project
            project.revenue = total_revenue
            project.actual_cost = total_cost
            project.progress = (total_cost / project.budget * 100) if project.budget > 0 else 0
            
            # Update or create budget
            budget = Budget.query.filter_by(project_id=project.id).first()
            if not budget:
                budget = Budget(
                    id=generate_id(),
                    project_id=project.id,
                    category='general',
                    amount=project.budget or 0,
                    month=datetime.now().strftime('%Y-%m'),
                    year=datetime.now().year,
                    status='active'
                )
                db.session.add(budget)
            
            budget.actual_amount = total_cost
            budget.calculate_variance()
            
            results.append({
                'project': project.name,
                'status': 'updated',
                'revenue': total_revenue,
                'cost': total_cost,
                'profit': total_revenue - total_cost,
                'entries': len(entries)
            })
        
        db.session.commit()
        return jsonify({
            'message': f'Updated {len(results)} projects',
            'results': results
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_all_project_data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400