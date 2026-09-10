from flask import request, jsonify
from models import WorkerTeam, TeamMember, db
from utils.helpers import generate_id
from routes import teams_bp
import random
import string

@teams_bp.route('', methods=['GET'])
def get_teams():
    """Get all teams"""
    try:
        teams = WorkerTeam.query.order_by(WorkerTeam.created_at.desc()).all()
        return jsonify([t.to_dict() for t in teams])
    except Exception as e:
        print(f"Error in get_teams: {str(e)}")
        return jsonify({'error': str(e)}), 500

@teams_bp.route('', methods=['POST'])
def create_team():
    """Create a new team"""
    try:
        data = request.json
        team = WorkerTeam(
            id=generate_id(),
            name=data.get('name'),
            site_id=data.get('siteId'),
            supervisor_id=data.get('supervisorId')
        )
        db.session.add(team)
        db.session.commit()
        return jsonify(team.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@teams_bp.route('/<team_id>', methods=['GET'])
def get_team(team_id):
    """Get a specific team"""
    try:
        team = WorkerTeam.query.get_or_404(team_id)
        return jsonify(team.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@teams_bp.route('/<team_id>', methods=['PUT'])
def update_team(team_id):
    """Update a team"""
    try:
        team = WorkerTeam.query.get_or_404(team_id)
        data = request.json
        
        team.name = data.get('name', team.name)
        team.site_id = data.get('siteId', team.site_id)
        team.supervisor_id = data.get('supervisorId', team.supervisor_id)
        
        db.session.commit()
        return jsonify(team.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@teams_bp.route('/<team_id>', methods=['DELETE'])
def delete_team(team_id):
    """Delete a team"""
    try:
        team = WorkerTeam.query.get_or_404(team_id)
        db.session.delete(team)
        db.session.commit()
        return jsonify({'message': 'Team deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@teams_bp.route('/<team_id>/members', methods=['POST'])
def add_team_member(team_id):
    """Add a member to a team"""
    try:
        team = WorkerTeam.query.get_or_404(team_id)
        data = request.json
        
        member = TeamMember(
            id=generate_id(),
            team_id=team_id,
            worker_id=data.get('workerId'),
            role_in_team=data.get('roleInTeam', '')
        )
        db.session.add(member)
        db.session.commit()
        return jsonify(member.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@teams_bp.route('/<team_id>/members/<member_id>', methods=['DELETE'])
def remove_team_member(team_id, member_id):
    """Remove a member from a team"""
    try:
        member = TeamMember.query.get_or_404(member_id)
        if member.team_id != team_id:
            return jsonify({'error': 'Member not in this team'}), 400
        
        db.session.delete(member)
        db.session.commit()
        return jsonify({'message': 'Member removed from team'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@teams_bp.route('/site/<site_id>', methods=['GET'])
def get_teams_by_site(site_id):
    """Get all teams for a specific site"""
    try:
        teams = WorkerTeam.query.filter_by(site_id=site_id).all()
        return jsonify([t.to_dict() for t in teams])
    except Exception as e:
        return jsonify({'error': str(e)}), 500