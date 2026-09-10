# routes/clients.py
from flask import request, jsonify
from models import db, Client, ClientContact, ClientCommunication, ClientProject, ClientPayment, ClientMeeting, ClientDocument, ClientSatisfaction, Project
from utils.helpers import generate_id
from routes import clients_bp
from datetime import datetime
import random
import string

# ============================================
# CLIENT CRUD OPERATIONS
# ============================================

@clients_bp.route('', methods=['GET'])
def get_clients():
    """Get all clients with filters"""
    try:
        status = request.args.get('status')
        priority = request.args.get('priority')
        search = request.args.get('search')
        
        query = Client.query
        
        if status:
            query = query.filter_by(status=status)
        if priority:
            query = query.filter_by(priority=priority)
        if search:
            query = query.filter(
                db.or_(
                    Client.name.ilike(f'%{search}%'),
                    Client.company_name.ilike(f'%{search}%'),
                    Client.email.ilike(f'%{search}%')
                )
            )
        
        clients = query.order_by(Client.name).all()
        
        result = []
        for client in clients:
            data = client.to_dict()
            # Get counts
            data['projectCount'] = client.projects.count()
            data['communicationCount'] = client.communications.count()
            data['paymentCount'] = client.payments.count()
            data['totalPayments'] = sum(p.amount for p in client.payments.all())
            result.append(data)
        
        return jsonify(result)
    except Exception as e:
        print(f"Error in get_clients: {str(e)}")
        return jsonify({'error': str(e)}), 500

@clients_bp.route('/<client_id>', methods=['GET'])
def get_client(client_id):
    """Get a specific client with all relations"""
    try:
        client = Client.query.get_or_404(client_id)
        return jsonify(client.to_dict_with_relations())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@clients_bp.route('', methods=['POST'])
def create_client():
    """Create a new client"""
    try:
        data = request.json
        
        client = Client(
            id=generate_id(),
            name=data.get('name'),
            company_name=data.get('companyName'),
            contact_person=data.get('contactPerson'),
            email=data.get('email'),
            phone=data.get('phone'),
            mobile=data.get('mobile'),
            address=data.get('address'),
            city=data.get('city'),
            country=data.get('country'),
            cr_number=data.get('crNumber'),
            vat_number=data.get('vatNumber'),
            website=data.get('website'),
            industry=data.get('industry'),
            client_type=data.get('clientType', 'company'),
            status=data.get('status', 'active'),
            priority=data.get('priority', 'medium'),
            rating=int(data.get('rating', 3)),
            notes=data.get('notes')
        )
        
        db.session.add(client)
        db.session.commit()
        
        return jsonify(client.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_client: {str(e)}")
        return jsonify({'error': str(e)}), 400

@clients_bp.route('/<client_id>', methods=['PUT'])
def update_client(client_id):
    """Update a client"""
    try:
        client = Client.query.get_or_404(client_id)
        data = request.json
        
        # Update fields
        if 'name' in data:
            client.name = data['name']
        if 'companyName' in data:
            client.company_name = data['companyName']
        if 'contactPerson' in data:
            client.contact_person = data['contactPerson']
        if 'email' in data:
            client.email = data['email']
        if 'phone' in data:
            client.phone = data['phone']
        if 'mobile' in data:
            client.mobile = data['mobile']
        if 'address' in data:
            client.address = data['address']
        if 'city' in data:
            client.city = data['city']
        if 'country' in data:
            client.country = data['country']
        if 'crNumber' in data:
            client.cr_number = data['crNumber']
        if 'vatNumber' in data:
            client.vat_number = data['vatNumber']
        if 'website' in data:
            client.website = data['website']
        if 'industry' in data:
            client.industry = data['industry']
        if 'clientType' in data:
            client.client_type = data['clientType']
        if 'status' in data:
            client.status = data['status']
        if 'priority' in data:
            client.priority = data['priority']
        if 'rating' in data:
            client.rating = int(data['rating'])
        if 'notes' in data:
            client.notes = data['notes']
        
        db.session.commit()
        return jsonify(client.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@clients_bp.route('/<client_id>', methods=['DELETE'])
def delete_client(client_id):
    """Delete a client"""
    try:
        client = Client.query.get_or_404(client_id)
        db.session.delete(client)
        db.session.commit()
        return jsonify({'message': 'Client deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# CLIENT CONTACTS
# ============================================

@clients_bp.route('/<client_id>/contacts', methods=['POST'])
def add_client_contact(client_id):
    """Add a contact to a client"""
    try:
        client = Client.query.get_or_404(client_id)
        data = request.json
        
        # If this is primary, unset other primary
        if data.get('isPrimary'):
            ClientContact.query.filter_by(client_id=client_id, is_primary=True).update({'is_primary': False})
        
        contact = ClientContact(
            id=generate_id(),
            client_id=client_id,
            name=data.get('name'),
            position=data.get('position'),
            email=data.get('email'),
            phone=data.get('phone'),
            mobile=data.get('mobile'),
            is_primary=data.get('isPrimary', False),
            notes=data.get('notes')
        )
        
        db.session.add(contact)
        db.session.commit()
        return jsonify(contact.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@clients_bp.route('/contacts/<contact_id>', methods=['PUT'])
def update_client_contact(contact_id):
    """Update a client contact"""
    try:
        contact = ClientContact.query.get_or_404(contact_id)
        data = request.json
        
        if 'name' in data:
            contact.name = data['name']
        if 'position' in data:
            contact.position = data['position']
        if 'email' in data:
            contact.email = data['email']
        if 'phone' in data:
            contact.phone = data['phone']
        if 'mobile' in data:
            contact.mobile = data['mobile']
        if 'isPrimary' in data and data['isPrimary']:
            # Unset other primary
            ClientContact.query.filter_by(client_id=contact.client_id, is_primary=True).update({'is_primary': False})
            contact.is_primary = True
        if 'notes' in data:
            contact.notes = data['notes']
        
        db.session.commit()
        return jsonify(contact.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@clients_bp.route('/contacts/<contact_id>', methods=['DELETE'])
def delete_client_contact(contact_id):
    """Delete a client contact"""
    try:
        contact = ClientContact.query.get_or_404(contact_id)
        db.session.delete(contact)
        db.session.commit()
        return jsonify({'message': 'Contact deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# CLIENT COMMUNICATIONS
# ============================================

@clients_bp.route('/<client_id>/communications', methods=['POST'])
def add_client_communication(client_id):
    """Add a communication record"""
    try:
        data = request.json
        
        communication = ClientCommunication(
            id=generate_id(),
            client_id=client_id,
            type=data.get('type'),
            direction=data.get('direction', 'outgoing'),
            subject=data.get('subject'),
            content=data.get('content'),
            date=datetime.fromisoformat(data.get('date')) if data.get('date') else datetime.now(),
            duration=data.get('duration'),
            status=data.get('status', 'completed'),
            follow_up_date=datetime.strptime(data.get('followUpDate'), '%Y-%m-%d').date() if data.get('followUpDate') else None,
            notes=data.get('notes'),
            created_by=data.get('createdBy')
        )
        
        db.session.add(communication)
        db.session.commit()
        return jsonify(communication.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@clients_bp.route('/communications', methods=['GET'])
def get_client_communications():
    """Get communications with filters"""
    try:
        client_id = request.args.get('clientId')
        type_filter = request.args.get('type')
        status_filter = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        
        query = ClientCommunication.query
        if client_id:
            query = query.filter_by(client_id=client_id)
        if type_filter:
            query = query.filter_by(type=type_filter)
        if status_filter:
            query = query.filter_by(status=status_filter)
        
        communications = query.order_by(ClientCommunication.date.desc()).limit(limit).all()
        return jsonify([c.to_dict() for c in communications])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# CLIENT PROJECTS
# ============================================

@clients_bp.route('/<client_id>/projects', methods=['POST'])
def link_client_project(client_id):
    """Link a client to a project"""
    try:
        data = request.json
        
        # Check if already linked
        existing = ClientProject.query.filter_by(
            client_id=client_id,
            project_id=data.get('projectId')
        ).first()
        
        if existing:
            return jsonify({'error': 'Client already linked to this project'}), 400
        
        client_project = ClientProject(
            id=generate_id(),
            client_id=client_id,
            project_id=data.get('projectId'),
            role=data.get('role', 'client'),
            status=data.get('status', 'active')
        )
        
        db.session.add(client_project)
        db.session.commit()
        return jsonify(client_project.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@clients_bp.route('/client-projects/<link_id>', methods=['DELETE'])
def unlink_client_project(link_id):
    """Unlink a client from a project"""
    try:
        link = ClientProject.query.get_or_404(link_id)
        db.session.delete(link)
        db.session.commit()
        return jsonify({'message': 'Project unlinked successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# CLIENT PAYMENTS
# ============================================

@clients_bp.route('/<client_id>/payments', methods=['POST'])
def add_client_payment(client_id):
    """Add a payment record"""
    try:
        data = request.json
        
        payment = ClientPayment(
            id=generate_id(),
            client_id=client_id,
            project_id=data.get('projectId'),
            invoice_id=data.get('invoiceId'),
            amount=float(data.get('amount')),
            payment_date=datetime.strptime(data.get('paymentDate'), '%Y-%m-%d').date(),
            payment_method=data.get('paymentMethod'),
            reference_number=data.get('referenceNumber'),
            status=data.get('status', 'completed'),
            notes=data.get('notes')
        )
        
        db.session.add(payment)
        db.session.commit()
        return jsonify(payment.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# CLIENT MEETINGS
# ============================================

@clients_bp.route('/<client_id>/meetings', methods=['POST'])
def add_client_meeting(client_id):
    """Add a meeting record"""
    try:
        data = request.json
        
        meeting = ClientMeeting(
            id=generate_id(),
            client_id=client_id,
            project_id=data.get('projectId'),
            title=data.get('title'),
            description=data.get('description'),
            meeting_date=datetime.fromisoformat(data.get('meetingDate')),
            duration=data.get('duration', 60),
            location=data.get('location'),
            meeting_type=data.get('meetingType', 'in_person'),
            status=data.get('status', 'scheduled'),
            minutes=data.get('minutes'),
            action_items=data.get('actionItems'),
            next_meeting_date=datetime.strptime(data.get('nextMeetingDate'), '%Y-%m-%d').date() if data.get('nextMeetingDate') else None,
            attendees=data.get('attendees'),
            created_by=data.get('createdBy')
        )
        
        db.session.add(meeting)
        db.session.commit()
        return jsonify(meeting.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# CLIENT SATISFACTION
# ============================================

@clients_bp.route('/<client_id>/satisfaction', methods=['POST'])
def add_client_satisfaction(client_id):
    """Add a satisfaction rating"""
    try:
        data = request.json
        
        satisfaction = ClientSatisfaction(
            id=generate_id(),
            client_id=client_id,
            project_id=data.get('projectId'),
            rating=int(data.get('rating')),
            category=data.get('category'),
            feedback=data.get('feedback'),
            survey_date=datetime.strptime(data.get('surveyDate'), '%Y-%m-%d').date()
        )
        
        db.session.add(satisfaction)
        db.session.commit()
        
        # Update client average rating
        client = Client.query.get(client_id)
        ratings = [s.rating for s in client.satisfactions.all()]
        if ratings:
            client.rating = int(sum(ratings) / len(ratings))
            db.session.commit()
        
        return jsonify(satisfaction.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# CLIENT SUMMARY
# ============================================

@clients_bp.route('/summary', methods=['GET'])
def get_client_summary():
    """Get client summary statistics"""
    try:
        total = Client.query.count()
        active = Client.query.filter_by(status='active').count()
        high_priority = Client.query.filter_by(priority='high').count()
        
        # Total payments
        total_payments = db.session.query(db.func.sum(ClientPayment.amount)).scalar() or 0
        
        # Average rating
        avg_rating = db.session.query(db.func.avg(Client.rating)).scalar() or 0
        
        return jsonify({
            'total': total,
            'active': active,
            'highPriority': high_priority,
            'totalPayments': total_payments,
            'averageRating': round(float(avg_rating), 1),
            'recentClients': [c.to_dict() for c in Client.query.order_by(Client.created_at.desc()).limit(5).all()]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500