# routes/quality_control.py
from flask import request, jsonify
from models import db, InspectionType, InspectionChecklist, Inspection, InspectionResult, Issue, CorrectiveAction, SafetyIncident, InspectionPhoto, Site, Project
from utils.helpers import generate_id
from routes import qc_bp
from datetime import datetime
import random
import string

# ============================================
# INSPECTION TYPES
# ============================================

@qc_bp.route('/inspection-types', methods=['GET'])
def get_inspection_types():
    try:
        types = InspectionType.query.all()
        return jsonify([t.to_dict() for t in types])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@qc_bp.route('/inspection-types', methods=['POST'])
def create_inspection_type():
    try:
        data = request.json
        insp_type = InspectionType(
            id=generate_id(),
            name=data.get('name'),
            category=data.get('category'),
            description=data.get('description'),
            frequency=data.get('frequency', 'daily')
        )
        db.session.add(insp_type)
        db.session.commit()
        return jsonify(insp_type.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# CHECKLISTS
# ============================================

@qc_bp.route('/checklists', methods=['GET'])
def get_checklists():
    try:
        inspection_type_id = request.args.get('inspectionTypeId')
        query = InspectionChecklist.query
        if inspection_type_id:
            query = query.filter_by(inspection_type_id=inspection_type_id)
        checklists = query.order_by(InspectionChecklist.order_index).all()
        return jsonify([c.to_dict() for c in checklists])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@qc_bp.route('/checklists', methods=['POST'])
def create_checklist():
    try:
        data = request.json
        checklist = InspectionChecklist(
            id=generate_id(),
            inspection_type_id=data.get('inspectionTypeId'),
            item=data.get('item'),
            category=data.get('category'),
            requirement=data.get('requirement'),
            is_mandatory=data.get('isMandatory', True),
            weightage=float(data.get('weightage', 0)),
            order_index=int(data.get('orderIndex', 0))
        )
        db.session.add(checklist)
        db.session.commit()
        return jsonify(checklist.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# INSPECTIONS
# ============================================

@qc_bp.route('/inspections', methods=['GET'])
def get_inspections():
    try:
        site_id = request.args.get('siteId')
        project_id = request.args.get('projectId')
        status = request.args.get('status')
        
        query = Inspection.query
        if site_id:
            query = query.filter_by(site_id=site_id)
        if project_id:
            query = query.filter_by(project_id=project_id)
        if status:
            query = query.filter_by(status=status)
        
        inspections = query.order_by(Inspection.inspection_date.desc()).all()
        return jsonify([i.to_dict() for i in inspections])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@qc_bp.route('/inspections', methods=['POST'])
def create_inspection():
    try:
        data = request.json
        
        inspection = Inspection(
            id=generate_id(),
            inspection_type_id=data.get('inspectionTypeId'),
            site_id=data.get('siteId'),
            project_id=data.get('projectId'),
            title=data.get('title'),
            description=data.get('description'),
            inspection_date=datetime.fromisoformat(data.get('inspectionDate')),
            conducted_by=data.get('conductedBy'),
            notes=data.get('notes')
        )
        
        db.session.add(inspection)
        db.session.commit()
        
        # Create results for checklist items
        checklists = InspectionChecklist.query.filter_by(inspection_type_id=inspection.inspection_type_id).all()
        for checklist in checklists:
            result = InspectionResult(
                id=generate_id(),
                inspection_id=inspection.id,
                checklist_item_id=checklist.id,
                result='pending'
            )
            db.session.add(result)
        
        db.session.commit()
        return jsonify(inspection.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@qc_bp.route('/inspections/<inspection_id>', methods=['GET'])
def get_inspection(inspection_id):
    try:
        inspection = Inspection.query.get_or_404(inspection_id)
        data = inspection.to_dict()
        data['results'] = [r.to_dict() for r in inspection.results.all()]
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@qc_bp.route('/inspections/<inspection_id>', methods=['PUT'])
def update_inspection(inspection_id):
    try:
        inspection = Inspection.query.get_or_404(inspection_id)
        data = request.json
        
        if 'status' in data:
            inspection.status = data['status']
        if 'notes' in data:
            inspection.notes = data['notes']
        if 'conductedBy' in data:
            inspection.conducted_by = data['conductedBy']
        
        db.session.commit()
        return jsonify(inspection.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@qc_bp.route('/inspections/<inspection_id>/results', methods=['PUT'])
def update_inspection_results(inspection_id):
    try:
        inspection = Inspection.query.get_or_404(inspection_id)
        data = request.json
        
        for result_data in data.get('results', []):
            result = InspectionResult.query.get(result_data.get('id'))
            if result and result.inspection_id == inspection_id:
                result.result = result_data.get('result', 'pending')
                result.notes = result_data.get('notes', '')
                result.score = float(result_data.get('score', 0))
        
        # Calculate scores and update status
        inspection.calculate_score()
        inspection.update_status()
        
        db.session.commit()
        return jsonify(inspection.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# ISSUES
# ============================================

@qc_bp.route('/issues', methods=['GET'])
def get_issues():
    try:
        site_id = request.args.get('siteId')
        project_id = request.args.get('projectId')
        status = request.args.get('status')
        severity = request.args.get('severity')
        
        query = Issue.query
        if site_id:
            query = query.filter_by(site_id=site_id)
        if project_id:
            query = query.filter_by(project_id=project_id)
        if status:
            query = query.filter_by(status=status)
        if severity:
            query = query.filter_by(severity=severity)
        
        issues = query.order_by(Issue.created_at.desc()).all()
        return jsonify([i.to_dict() for i in issues])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@qc_bp.route('/issues', methods=['POST'])
def create_issue():
    try:
        data = request.json
        issue = Issue(
            id=generate_id(),
            inspection_id=data.get('inspectionId'),
            site_id=data.get('siteId'),
            project_id=data.get('projectId'),
            title=data.get('title'),
            description=data.get('description'),
            severity=data.get('severity', 'medium'),
            category=data.get('category'),
            location=data.get('location'),
            reported_by=data.get('reportedBy'),
            assigned_to=data.get('assignedTo'),
            due_date=datetime.strptime(data.get('dueDate'), '%Y-%m-%d').date() if data.get('dueDate') else None
        )
        db.session.add(issue)
        db.session.commit()
        return jsonify(issue.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@qc_bp.route('/issues/<issue_id>', methods=['PUT'])
def update_issue(issue_id):
    try:
        issue = Issue.query.get_or_404(issue_id)
        data = request.json
        
        if 'status' in data:
            issue.status = data['status']
        if 'assignedTo' in data:
            issue.assigned_to = data['assignedTo']
        if 'resolutionNotes' in data:
            issue.resolution_notes = data['resolutionNotes']
        
        db.session.commit()
        return jsonify(issue.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# CORRECTIVE ACTIONS
# ============================================

@qc_bp.route('/issues/<issue_id>/actions', methods=['POST'])
def add_corrective_action(issue_id):
    try:
        data = request.json
        action = CorrectiveAction(
            id=generate_id(),
            issue_id=issue_id,
            description=data.get('description'),
            action_plan=data.get('actionPlan'),
            assigned_to=data.get('assignedTo'),
            due_date=datetime.strptime(data.get('dueDate'), '%Y-%m-%d').date() if data.get('dueDate') else None
        )
        db.session.add(action)
        db.session.commit()
        return jsonify(action.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# SAFETY INCIDENTS
# ============================================

@qc_bp.route('/safety-incidents', methods=['GET'])
def get_safety_incidents():
    try:
        site_id = request.args.get('siteId')
        project_id = request.args.get('projectId')
        incident_type = request.args.get('incidentType')
        
        query = SafetyIncident.query
        if site_id:
            query = query.filter_by(site_id=site_id)
        if project_id:
            query = query.filter_by(project_id=project_id)
        if incident_type:
            query = query.filter_by(incident_type=incident_type)
        
        incidents = query.order_by(SafetyIncident.incident_date.desc()).all()
        return jsonify([i.to_dict() for i in incidents])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@qc_bp.route('/safety-incidents', methods=['POST'])
def create_safety_incident():
    try:
        data = request.json
        incident = SafetyIncident(
            id=generate_id(),
            site_id=data.get('siteId'),
            project_id=data.get('projectId'),
            title=data.get('title'),
            description=data.get('description'),
            incident_type=data.get('incidentType'),
            severity=data.get('severity', 'medium'),
            incident_date=datetime.fromisoformat(data.get('incidentDate')),
            location=data.get('location'),
            reported_by=data.get('reportedBy'),
            witnesses=data.get('witnesses'),
            immediate_action=data.get('immediateAction'),
            notes=data.get('notes')
        )
        db.session.add(incident)
        db.session.commit()
        return jsonify(incident.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@qc_bp.route('/safety-incidents/<incident_id>', methods=['PUT'])
def update_safety_incident(incident_id):
    try:
        incident = SafetyIncident.query.get_or_404(incident_id)
        data = request.json
        
        if 'status' in data:
            incident.status = data['status']
        if 'rootCause' in data:
            incident.root_cause = data['rootCause']
        if 'correctiveAction' in data:
            incident.corrective_action = data['correctiveAction']
        if 'investigationCompleted' in data:
            incident.investigation_completed = data['investigationCompleted']
        
        db.session.commit()
        return jsonify(incident.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# SUMMARY
# ============================================

@qc_bp.route('/summary', methods=['GET'])
def get_qc_summary():
    try:
        site_id = request.args.get('siteId')
        
        query_inspections = Inspection.query
        query_issues = Issue.query
        query_incidents = SafetyIncident.query
        
        if site_id:
            query_inspections = query_inspections.filter_by(site_id=site_id)
            query_issues = query_issues.filter_by(site_id=site_id)
            query_incidents = query_incidents.filter_by(site_id=site_id)
        
        total_inspections = query_inspections.count()
        completed_inspections = query_inspections.filter_by(status='completed').count()
        pending_review = query_inspections.filter_by(status='pending_review').count()
        
        open_issues = query_issues.filter_by(status='open').count()
        in_progress_issues = query_issues.filter_by(status='in_progress').count()
        resolved_issues = query_issues.filter_by(status='resolved').count()
        
        critical_issues = query_issues.filter_by(severity='critical').count()
        high_issues = query_issues.filter_by(severity='high').count()
        
        total_incidents = query_incidents.count()
        
        return jsonify({
            'totalInspections': total_inspections,
            'completedInspections': completed_inspections,
            'pendingReview': pending_review,
            'openIssues': open_issues,
            'inProgressIssues': in_progress_issues,
            'resolvedIssues': resolved_issues,
            'criticalIssues': critical_issues,
            'highIssues': high_issues,
            'totalIncidents': total_incidents,
            'passRate': (completed_inspections / total_inspections * 100) if total_inspections > 0 else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500