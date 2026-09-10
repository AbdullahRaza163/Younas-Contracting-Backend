# routes/projects.py
from flask import request, jsonify
from models import db, Project, Entry, Site, Worker
from utils.helpers import generate_id
from routes import projects_bp
from datetime import datetime
import random
import string

@projects_bp.route('', methods=['GET'])
def get_projects():
    """Get all projects with optional filters"""
    try:
        status = request.args.get('status')
        priority = request.args.get('priority')
        site_id = request.args.get('siteId')
        
        query = Project.query
        
        if status:
            query = query.filter_by(status=status)
        if priority:
            query = query.filter_by(priority=priority)
        if site_id:
            query = query.filter_by(site_id=site_id)
        
        projects = query.order_by(Project.created_at.desc()).all()
        
        result = []
        for project in projects:
            project_dict = project.to_dict()
            
            # Calculate financials from entries using site_id as proxy
            # Since project_id doesn't exist yet, we'll use site_id
            entries = Entry.query.filter_by(site_id=project.site_id).all()
            total_revenue = sum(e.kamai or 0 for e in entries)
            total_cost = sum(
                (e.labour or 0) + 
                (e.material_cost or 0) + 
                (e.equipment_cost or 0) + 
                (e.transport_cost or 0) + 
                (e.other_expense or 0)
                for e in entries
            )
            
            project_dict['revenue'] = total_revenue
            project_dict['actualCost'] = total_cost
            project_dict['profit'] = total_revenue - total_cost
            project_dict['profitMargin'] = ((total_revenue - total_cost) / total_revenue * 100) if total_revenue > 0 else 0
            
            # Calculate progress based on budget
            if project.budget > 0:
                progress = (total_cost / project.budget) * 100
                project_dict['progress'] = min(progress, 100)
            
            result.append(project_dict)
        
        return jsonify(result)
    except Exception as e:
        print(f"Error in get_projects: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@projects_bp.route('/<project_id>', methods=['GET'])
def get_project(project_id):
    """Get a specific project"""
    try:
        project = Project.query.get_or_404(project_id)
        result = project.to_dict()
        
        # Calculate financials
        entries = Entry.query.filter_by(site_id=project.site_id).all()
        total_revenue = sum(e.kamai or 0 for e in entries)
        total_cost = sum(
            (e.labour or 0) + 
            (e.material_cost or 0) + 
            (e.equipment_cost or 0) + 
            (e.transport_cost or 0) + 
            (e.other_expense or 0)
            for e in entries
        )
        
        result['revenue'] = total_revenue
        result['actualCost'] = total_cost
        result['profit'] = total_revenue - total_cost
        result['profitMargin'] = ((total_revenue - total_cost) / total_revenue * 100) if total_revenue > 0 else 0
        
        if project.budget > 0:
            progress = (total_cost / project.budget) * 100
            result['progress'] = min(progress, 100)
        
        return jsonify(result)
    except Exception as e:
        print(f"Error in get_project: {str(e)}")
        return jsonify({'error': str(e)}), 404

@projects_bp.route('', methods=['POST'])
def create_project():
    """Create a new project"""
    try:
        data = request.json
        
        project = Project(
            id=generate_id(),
            name=data.get('name'),
            description=data.get('description'),
            code=Project.generate_code(),
            client=data.get('client'),
            client_contact=data.get('clientContact'),
            client_phone=data.get('clientPhone'),
            client_email=data.get('clientEmail'),
            site_id=data.get('siteId'),
            budget=float(data.get('budget', 0)),
            start_date=datetime.strptime(data.get('startDate'), '%Y-%m-%d').date() if data.get('startDate') else None,
            end_date=datetime.strptime(data.get('endDate'), '%Y-%m-%d').date() if data.get('endDate') else None,
            status=data.get('status', 'planning'),
            priority=data.get('priority', 'medium'),
            project_manager=data.get('projectManager'),
            team_lead=data.get('teamLead'),
            notes=data.get('notes'),
            risk_level=data.get('riskLevel', 'low'),
            health_status='planning'
        )
        
        db.session.add(project)
        db.session.commit()
        
        result = project.to_dict()
        result['revenue'] = 0
        result['actualCost'] = 0
        result['profit'] = 0
        result['profitMargin'] = 0
        
        return jsonify(result), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_project: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400

@projects_bp.route('/<project_id>', methods=['PUT'])
def update_project(project_id):
    """Update a project"""
    try:
        project = Project.query.get_or_404(project_id)
        data = request.json
        
        # Update fields
        if 'name' in data:
            project.name = data['name']
        if 'description' in data:
            project.description = data['description']
        if 'client' in data:
            project.client = data['client']
        if 'clientContact' in data:
            project.client_contact = data['clientContact']
        if 'clientPhone' in data:
            project.client_phone = data['clientPhone']
        if 'clientEmail' in data:
            project.client_email = data['clientEmail']
        if 'siteId' in data:
            project.site_id = data['siteId']
        if 'budget' in data:
            project.budget = float(data['budget'])
        if 'startDate' in data and data['startDate']:
            project.start_date = datetime.strptime(data['startDate'], '%Y-%m-%d').date()
        if 'endDate' in data and data['endDate']:
            project.end_date = datetime.strptime(data['endDate'], '%Y-%m-%d').date()
        if 'status' in data:
            project.status = data['status']
        if 'priority' in data:
            project.priority = data['priority']
        if 'projectManager' in data:
            project.project_manager = data['projectManager']
        if 'teamLead' in data:
            project.team_lead = data['teamLead']
        if 'notes' in data:
            project.notes = data['notes']
        if 'riskLevel' in data:
            project.risk_level = data['riskLevel']
        
        db.session.commit()
        
        result = project.to_dict()
        
        # Calculate financials
        entries = Entry.query.filter_by(site_id=project.site_id).all()
        total_revenue = sum(e.kamai or 0 for e in entries)
        total_cost = sum(
            (e.labour or 0) + 
            (e.material_cost or 0) + 
            (e.equipment_cost or 0) + 
            (e.transport_cost or 0) + 
            (e.other_expense or 0)
            for e in entries
        )
        
        result['revenue'] = total_revenue
        result['actualCost'] = total_cost
        result['profit'] = total_revenue - total_cost
        result['profitMargin'] = ((total_revenue - total_cost) / total_revenue * 100) if total_revenue > 0 else 0
        
        if project.budget > 0:
            progress = (total_cost / project.budget) * 100
            result['progress'] = min(progress, 100)
        
        return jsonify(result)
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_project: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400

@projects_bp.route('/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project"""
    try:
        project = Project.query.get_or_404(project_id)
        db.session.delete(project)
        db.session.commit()
        return jsonify({'message': 'Project deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@projects_bp.route('/summary', methods=['GET'])
def get_project_summary():
    """Get project summary statistics"""
    try:
        total = Project.query.count()
        active = Project.query.filter(Project.status.in_(['planning', 'active'])).count()
        completed = Project.query.filter_by(status='completed').count()
        overdue = Project.query.filter(
            Project.end_date < datetime.now().date(),
            Project.status != 'completed'
        ).count()
        
        # Financial summary
        all_projects = Project.query.all()
        total_budget = sum(p.budget for p in all_projects)
        
        # Calculate actual costs from entries by site
        total_actual = 0
        total_revenue = 0
        for project in all_projects:
            entries = Entry.query.filter_by(site_id=project.site_id).all()
            total_actual += sum(
                (e.labour or 0) + 
                (e.material_cost or 0) + 
                (e.equipment_cost or 0) + 
                (e.transport_cost or 0) + 
                (e.other_expense or 0)
                for e in entries
            )
            total_revenue += sum(e.kamai or 0 for e in entries)
        
        return jsonify({
            'total': total,
            'active': active,
            'completed': completed,
            'overdue': overdue,
            'totalBudget': total_budget,
            'totalActual': total_actual,
            'totalRevenue': total_revenue,
            'totalProfit': total_revenue - total_actual,
            'overallProgress': (total_actual / total_budget * 100) if total_budget > 0 else 0
        })
    except Exception as e:
        print(f"Error in get_project_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500