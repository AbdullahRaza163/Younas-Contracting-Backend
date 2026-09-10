# models/client.py
from models import db
from datetime import datetime
import random
import string

class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    company_name = db.Column(db.String(200))
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    cr_number = db.Column(db.String(50))
    vat_number = db.Column(db.String(50))
    website = db.Column(db.String(200))
    industry = db.Column(db.String(100))
    client_type = db.Column(db.String(50), default='company')
    status = db.Column(db.String(20), default='active')
    priority = db.Column(db.String(20), default='medium')
    rating = db.Column(db.Integer, default=3)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contacts = db.relationship('ClientContact', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    communications = db.relationship('ClientCommunication', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    projects = db.relationship('ClientProject', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    payments = db.relationship('ClientPayment', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    meetings = db.relationship('ClientMeeting', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    documents = db.relationship('ClientDocument', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    satisfactions = db.relationship('ClientSatisfaction', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'companyName': self.company_name,
            'contactPerson': self.contact_person,
            'email': self.email,
            'phone': self.phone,
            'mobile': self.mobile,
            'address': self.address,
            'city': self.city,
            'country': self.country,
            'crNumber': self.cr_number,
            'vatNumber': self.vat_number,
            'website': self.website,
            'industry': self.industry,
            'clientType': self.client_type,
            'status': self.status,
            'priority': self.priority,
            'rating': self.rating,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def to_dict_with_relations(self):
        data = self.to_dict()
        data['contacts'] = [c.to_dict() for c in self.contacts.all()]
        data['communications'] = [c.to_dict() for c in self.communications.all()]
        data['projects'] = [p.to_dict() for p in self.projects.all()]
        data['payments'] = [p.to_dict() for p in self.payments.all()]
        data['meetings'] = [m.to_dict() for m in self.meetings.all()]
        data['documents'] = [d.to_dict() for d in self.documents.all()]
        data['satisfactions'] = [s.to_dict() for s in self.satisfactions.all()]
        return data
    
    @staticmethod
    def get_active_clients():
        return Client.query.filter_by(status='active').all()
    
    @staticmethod
    def get_by_priority(priority):
        return Client.query.filter_by(priority=priority).all()
    
    @staticmethod
    def search(search_term):
        return Client.query.filter(
            db.or_(
                Client.name.ilike(f'%{search_term}%'),
                Client.company_name.ilike(f'%{search_term}%'),
                Client.email.ilike(f'%{search_term}%')
            )
        ).all()


class ClientContact(db.Model):
    __tablename__ = 'client_contacts'
    
    id = db.Column(db.String(20), primary_key=True)
    client_id = db.Column(db.String(20), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    is_primary = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'clientId': self.client_id,
            'name': self.name,
            'position': self.position,
            'email': self.email,
            'phone': self.phone,
            'mobile': self.mobile,
            'isPrimary': self.is_primary,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }


class ClientCommunication(db.Model):
    __tablename__ = 'client_communications'
    
    id = db.Column(db.String(20), primary_key=True)
    client_id = db.Column(db.String(20), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    direction = db.Column(db.String(20), default='outgoing')
    subject = db.Column(db.String(200))
    content = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    duration = db.Column(db.Integer)
    status = db.Column(db.String(50), default='completed')
    follow_up_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'clientId': self.client_id,
            'type': self.type,
            'direction': self.direction,
            'subject': self.subject,
            'content': self.content,
            'date': self.date.isoformat() if self.date else None,
            'duration': self.duration,
            'status': self.status,
            'followUpDate': self.follow_up_date.isoformat() if self.follow_up_date else None,
            'notes': self.notes,
            'createdBy': self.created_by,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }


class ClientProject(db.Model):
    __tablename__ = 'client_projects'
    
    id = db.Column(db.String(20), primary_key=True)
    client_id = db.Column(db.String(20), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    role = db.Column(db.String(50), default='client')
    status = db.Column(db.String(20), default='active')
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    project = db.relationship('Project', backref='client_projects')
    
    __table_args__ = (db.UniqueConstraint('client_id', 'project_id', name='unique_client_project'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'clientId': self.client_id,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'role': self.role,
            'status': self.status,
            'assignedAt': self.assigned_at.isoformat() if self.assigned_at else None,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class ClientPayment(db.Model):
    __tablename__ = 'client_payments'
    
    id = db.Column(db.String(20), primary_key=True)
    client_id = db.Column(db.String(20), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='SET NULL'))
    invoice_id = db.Column(db.String(20), db.ForeignKey('invoices.id', ondelete='SET NULL'))
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50))
    reference_number = db.Column(db.String(100))
    status = db.Column(db.String(20), default='completed')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = db.relationship('Project', backref='client_payments')
    invoice = db.relationship('Invoice', backref='client_payments')
    
    def to_dict(self):
        return {
            'id': self.id,
            'clientId': self.client_id,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'invoiceId': self.invoice_id,
            'amount': self.amount,
            'paymentDate': self.payment_date.isoformat() if self.payment_date else None,
            'paymentMethod': self.payment_method,
            'referenceNumber': self.reference_number,
            'status': self.status,
            'notes': self.notes,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }


class ClientMeeting(db.Model):
    __tablename__ = 'client_meetings'
    
    id = db.Column(db.String(20), primary_key=True)
    client_id = db.Column(db.String(20), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='SET NULL'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    meeting_date = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer, default=60)
    location = db.Column(db.String(200))
    meeting_type = db.Column(db.String(50), default='in_person')
    status = db.Column(db.String(20), default='scheduled')
    minutes = db.Column(db.Text)
    action_items = db.Column(db.Text)
    next_meeting_date = db.Column(db.Date)
    attendees = db.Column(db.Text)
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = db.relationship('Project', backref='client_meetings')
    
    def to_dict(self):
        return {
            'id': self.id,
            'clientId': self.client_id,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'title': self.title,
            'description': self.description,
            'meetingDate': self.meeting_date.isoformat() if self.meeting_date else None,
            'duration': self.duration,
            'location': self.location,
            'meetingType': self.meeting_type,
            'status': self.status,
            'minutes': self.minutes,
            'actionItems': self.action_items,
            'nextMeetingDate': self.next_meeting_date.isoformat() if self.next_meeting_date else None,
            'attendees': self.attendees,
            'createdBy': self.created_by,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }


class ClientDocument(db.Model):
    __tablename__ = 'client_documents'
    
    id = db.Column(db.String(20), primary_key=True)
    client_id = db.Column(db.String(20), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(50))
    file_url = db.Column(db.Text)
    file_name = db.Column(db.String(200))
    file_size = db.Column(db.Integer)
    description = db.Column(db.Text)
    uploaded_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'clientId': self.client_id,
            'name': self.name,
            'type': self.type,
            'fileUrl': self.file_url,
            'fileName': self.file_name,
            'fileSize': self.file_size,
            'description': self.description,
            'uploadedBy': self.uploaded_by,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }


class ClientSatisfaction(db.Model):
    __tablename__ = 'client_satisfaction'
    
    id = db.Column(db.String(20), primary_key=True)
    client_id = db.Column(db.String(20), db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.String(20), db.ForeignKey('projects.id', ondelete='SET NULL'))
    rating = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50))
    feedback = db.Column(db.Text)
    survey_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    project = db.relationship('Project', backref='client_satisfactions')
    
    def to_dict(self):
        return {
            'id': self.id,
            'clientId': self.client_id,
            'projectId': self.project_id,
            'projectName': self.project.name if self.project else None,
            'rating': self.rating,
            'category': self.category,
            'feedback': self.feedback,
            'surveyDate': self.survey_date.isoformat() if self.survey_date else None,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }