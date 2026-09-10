# models/quality_control.py
from models import db
from datetime import datetime
import random
import string

class InspectionType(db.Model):
    __tablename__ = 'inspection_types'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    frequency = db.Column(db.String(20), default='daily')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    checklists = db.relationship('InspectionChecklist', backref='inspection_type', lazy='dynamic', cascade='all, delete-orphan')
    inspections = db.relationship('Inspection', backref='inspection_type', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'frequency': self.frequency,
            'isActive': self.is_active,
            'checklistCount': self.checklists.count(),
            'inspectionCount': self.inspections.count(),
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }

class InspectionChecklist(db.Model):
    __tablename__ = 'inspection_checklists'
    
    id = db.Column(db.String(20), primary_key=True)
    inspection_type_id = db.Column(db.String(20), db.ForeignKey('inspection_types.id', ondelete='CASCADE'), nullable=False)
    item = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))
    requirement = db.Column(db.Text)
    is_mandatory = db.Column(db.Boolean, default=True)
    weightage = db.Column(db.Float, default=0.0)
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'inspectionTypeId': self.inspection_type_id,
            'item': self.item,
            'category': self.category,
            'requirement': self.requirement,
            'isMandatory': self.is_mandatory,
            'weightage': self.weightage,
            'orderIndex': self.order_index,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }

class Inspection(db.Model):
    __tablename__ = 'inspections'
    
    id = db.Column(db.String(20), primary_key=True)
    inspection_type_id = db.Column(db.String(20), db.ForeignKey('inspection_types.id', ondelete='SET NULL'))
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='SET NULL'))
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='SET NULL'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    inspection_date = db.Column(db.DateTime, nullable=False)
    conducted_by = db.Column(db.String(100))
    status = db.Column(db.String(20), default='in_progress')
    overall_rating = db.Column(db.Integer, default=0)
    score = db.Column(db.Float, default=0.0)
    total_items = db.Column(db.Integer, default=0)
    passed_items = db.Column(db.Integer, default=0)
    failed_items = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    site = db.relationship('Site', backref='inspections')
    project = db.relationship('Project', backref='inspections')
    results = db.relationship('InspectionResult', backref='inspection', lazy='dynamic', cascade='all, delete-orphan')
    photos = db.relationship('InspectionPhoto', backref='inspection', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'inspectionTypeId': self.inspection_type_id,
            'inspectionTypeName': self.inspection_type.name if self.inspection_type else None,
            'siteId': self.site_id,
            'siteName': self.site.name if self.site else None,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'title': self.title,
            'description': self.description,
            'inspectionDate': self.inspection_date.isoformat() if self.inspection_date else None,
            'conductedBy': self.conducted_by,
            'status': self.status,
            'overallRating': self.overall_rating,
            'score': self.score,
            'totalItems': self.total_items,
            'passedItems': self.passed_items,
            'failedItems': self.failed_items,
            'notes': self.notes,
            'resultCount': self.results.count(),
            'photoCount': self.photos.count(),
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_score(self):
        """Calculate inspection score based on results"""
        results = self.results.all()
        if not results:
            return 0
        
        total_weightage = 0
        earned_score = 0
        
        for result in results:
            if result.checklist_item:
                weightage = result.checklist_item.weightage or 0
                total_weightage += weightage
                if result.result == 'pass':
                    earned_score += weightage
        
        self.score = (earned_score / total_weightage * 100) if total_weightage > 0 else 0
        self.total_items = len(results)
        self.passed_items = sum(1 for r in results if r.result == 'pass')
        self.failed_items = sum(1 for r in results if r.result == 'fail')
        
        # Update overall rating (1-5)
        if self.score >= 90:
            self.overall_rating = 5
        elif self.score >= 75:
            self.overall_rating = 4
        elif self.score >= 60:
            self.overall_rating = 3
        elif self.score >= 40:
            self.overall_rating = 2
        else:
            self.overall_rating = 1
        
        return self.score
    
    def update_status(self):
        """Update inspection status based on results"""
        if self.failed_items == 0 and self.total_items > 0:
            self.status = 'approved'
        elif self.failed_items > 0:
            self.status = 'pending_review'
        return self.status

class InspectionResult(db.Model):
    __tablename__ = 'inspection_results'
    
    id = db.Column(db.String(20), primary_key=True)
    inspection_id = db.Column(db.String(20), db.ForeignKey('inspections.id', ondelete='CASCADE'), nullable=False)
    checklist_item_id = db.Column(db.String(20), db.ForeignKey('inspection_checklists.id', ondelete='SET NULL'))
    result = db.Column(db.String(20), default='pending')
    notes = db.Column(db.Text)
    score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    checklist_item = db.relationship('InspectionChecklist', backref='results')
    
    def to_dict(self):
        return {
            'id': self.id,
            'inspectionId': self.inspection_id,
            'checklistItemId': self.checklist_item_id,
            'checklistItem': self.checklist_item.item if self.checklist_item else None,
            'category': self.checklist_item.category if self.checklist_item else None,
            'isMandatory': self.checklist_item.is_mandatory if self.checklist_item else True,
            'result': self.result,
            'notes': self.notes,
            'score': self.score,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }

class Issue(db.Model):
    __tablename__ = 'issues'
    
    id = db.Column(db.String(20), primary_key=True)
    inspection_id = db.Column(db.String(20), db.ForeignKey('inspections.id', ondelete='SET NULL'))
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='SET NULL'))
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='SET NULL'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    severity = db.Column(db.String(20), default='medium')
    status = db.Column(db.String(20), default='open')
    category = db.Column(db.String(50))
    location = db.Column(db.String(200))
    reported_by = db.Column(db.String(100))
    assigned_to = db.Column(db.String(100))
    due_date = db.Column(db.Date)
    resolution_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    site = db.relationship('Site', backref='issues')
    project = db.relationship('Project', backref='issues')
    corrective_actions = db.relationship('CorrectiveAction', backref='issue', lazy='dynamic', cascade='all, delete-orphan')
    photos = db.relationship('InspectionPhoto', backref='issue', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'inspectionId': self.inspection_id,
            'siteId': self.site_id,
            'siteName': self.site.name if self.site else None,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'title': self.title,
            'description': self.description,
            'severity': self.severity,
            'status': self.status,
            'category': self.category,
            'location': self.location,
            'reportedBy': self.reported_by,
            'assignedTo': self.assigned_to,
            'dueDate': self.due_date.isoformat() if self.due_date else None,
            'resolutionNotes': self.resolution_notes,
            'actionCount': self.corrective_actions.count(),
            'photoCount': self.photos.count(),
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }

class CorrectiveAction(db.Model):
    __tablename__ = 'corrective_actions'
    
    id = db.Column(db.String(20), primary_key=True)
    issue_id = db.Column(db.String(20), db.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    action_plan = db.Column(db.Text)
    assigned_to = db.Column(db.String(100))
    due_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='pending')
    verification_notes = db.Column(db.Text)
    completed_date = db.Column(db.Date)
    verified_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'issueId': self.issue_id,
            'description': self.description,
            'actionPlan': self.action_plan,
            'assignedTo': self.assigned_to,
            'dueDate': self.due_date.isoformat() if self.due_date else None,
            'status': self.status,
            'verificationNotes': self.verification_notes,
            'completedDate': self.completed_date.isoformat() if self.completed_date else None,
            'verifiedBy': self.verified_by,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }

class SafetyIncident(db.Model):
    __tablename__ = 'safety_incidents'
    
    id = db.Column(db.String(20), primary_key=True)
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='SET NULL'))
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='SET NULL'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    incident_type = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(20), default='medium')
    incident_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))
    reported_by = db.Column(db.String(100))
    witnesses = db.Column(db.Text)
    immediate_action = db.Column(db.Text)
    root_cause = db.Column(db.Text)
    corrective_action = db.Column(db.Text)
    status = db.Column(db.String(20), default='under_investigation')
    investigation_completed = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    site = db.relationship('Site', backref='safety_incidents')
    project = db.relationship('Project', backref='safety_incidents')
    
    def to_dict(self):
        return {
            'id': self.id,
            'siteId': self.site_id,
            'siteName': self.site.name if self.site else None,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'title': self.title,
            'description': self.description,
            'incidentType': self.incident_type,
            'severity': self.severity,
            'incidentDate': self.incident_date.isoformat() if self.incident_date else None,
            'location': self.location,
            'reportedBy': self.reported_by,
            'witnesses': self.witnesses,
            'immediateAction': self.immediate_action,
            'rootCause': self.root_cause,
            'correctiveAction': self.corrective_action,
            'status': self.status,
            'investigationCompleted': self.investigation_completed,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }

class InspectionPhoto(db.Model):
    __tablename__ = 'inspection_photos'
    
    id = db.Column(db.String(20), primary_key=True)
    inspection_id = db.Column(db.String(20), db.ForeignKey('inspections.id', ondelete='CASCADE'))
    issue_id = db.Column(db.String(20), db.ForeignKey('issues.id', ondelete='SET NULL'))
    photo_url = db.Column(db.Text, nullable=False)
    caption = db.Column(db.Text)
    uploaded_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'inspectionId': self.inspection_id,
            'issueId': self.issue_id,
            'photoUrl': self.photo_url,
            'caption': self.caption,
            'uploadedBy': self.uploaded_by,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }