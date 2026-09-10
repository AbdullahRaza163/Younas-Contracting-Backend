# models/team.py
from models import db
from datetime import datetime
import random
import string

class WorkerTeam(db.Model):
    __tablename__ = 'worker_teams'
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='CASCADE'))
    supervisor_id = db.Column(db.String(20), db.ForeignKey('workers.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Make updated_at nullable for existing records
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    
    # Relationships - using the backref names from worker.py
    members = db.relationship('TeamMember', backref='team', lazy='dynamic', cascade='all, delete-orphan')
    # supervisor_ref is defined in worker.py - DO NOT define supervisor relationship here
    
    def to_dict(self):
        # Get supervisor from the supervisor_ref relationship (defined in Worker model)
        supervisor = self.supervisor_ref if hasattr(self, 'supervisor_ref') else None
        # Get site from the site_ref relationship (defined in Site model)
        site = self.site_ref if hasattr(self, 'site_ref') else None
        
        return {
            'id': self.id,
            'name': self.name,
            'siteId': self.site_id,
            'siteName': site.name if site else None,
            'supervisorId': self.supervisor_id,
            'supervisorName': supervisor.name if supervisor else None,
            'members': [m.to_dict() for m in self.members.all()] if self.members else [],
            'memberCount': self.members.count() if self.members else 0,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def add_member(self, worker_id, role_in_team=None):
        """Add a worker to the team"""
        existing = TeamMember.query.filter_by(team_id=self.id, worker_id=worker_id).first()
        if existing:
            return existing
        
        member = TeamMember(
            id=''.join(random.choices(string.ascii_lowercase + string.digits, k=9)),
            team_id=self.id,
            worker_id=worker_id,
            role_in_team=role_in_team
        )
        db.session.add(member)
        return member
    
    def remove_member(self, member_id):
        """Remove a member from the team"""
        member = TeamMember.query.get(member_id)
        if member and member.team_id == self.id:
            db.session.delete(member)
            return True
        return False
    
    def remove_member_by_worker(self, worker_id):
        """Remove a member by worker ID"""
        member = TeamMember.query.filter_by(team_id=self.id, worker_id=worker_id).first()
        if member:
            db.session.delete(member)
            return True
        return False
    
    def get_team_members(self):
        """Get all members of the team with their details"""
        return [m.to_dict() for m in self.members.all()] if self.members else []
    
    def get_worker_ids(self):
        """Get all worker IDs in the team"""
        return [m.worker_id for m in self.members.all()] if self.members else []
    
    def get_member_count(self):
        """Get the number of members in the team"""
        return self.members.count() if self.members else 0
    
    def is_member(self, worker_id):
        """Check if a worker is a member of this team"""
        return TeamMember.query.filter_by(team_id=self.id, worker_id=worker_id).first() is not None
    
    def get_attendance_for_date(self, date):
        """Get attendance for all team members on a specific date"""
        from .attendance import Attendance
        worker_ids = self.get_worker_ids()
        if not worker_ids:
            return []
        return Attendance.query.filter(
            Attendance.worker_id.in_(worker_ids),
            Attendance.date == date
        ).all()
    
    def get_attendance_summary(self, start_date, end_date):
        """Get attendance summary for the team over a date range"""
        from .attendance import Attendance
        worker_ids = self.get_worker_ids()
        if not worker_ids:
            return {
                'total_members': 0,
                'total_days': 0,
                'total_present': 0,
                'total_hours': 0,
                'total_wages': 0,
                'attendance_rate': 0
            }
        
        records = Attendance.query.filter(
            Attendance.worker_id.in_(worker_ids),
            Attendance.date >= start_date,
            Attendance.date <= end_date
        ).all()
        
        total_days = (end_date - start_date).days + 1
        total_possible = len(worker_ids) * total_days
        total_present = sum(1 for r in records if r.present)
        total_hours = sum(r.total_hours or 0 for r in records)
        total_wages = sum(r.wage_earned or 0 for r in records)
        
        return {
            'total_members': len(worker_ids),
            'total_days': total_days,
            'total_possible': total_possible,
            'total_present': total_present,
            'total_absent': total_possible - total_present,
            'total_hours': total_hours,
            'total_wages': total_wages,
            'attendance_rate': (total_present / total_possible * 100) if total_possible > 0 else 0
        }
    
    @staticmethod
    def get_all_teams():
        """Get all teams"""
        return WorkerTeam.query.all()
    
    @staticmethod
    def get_team_by_id(team_id):
        """Get a team by ID"""
        return WorkerTeam.query.get(team_id)
    
    @staticmethod
    def get_teams_by_site(site_id):
        """Get all teams for a site"""
        return WorkerTeam.query.filter_by(site_id=site_id).all()
    
    @staticmethod
    def get_teams_by_supervisor(supervisor_id):
        """Get all teams supervised by a worker"""
        return WorkerTeam.query.filter_by(supervisor_id=supervisor_id).all()
    
    @staticmethod
    def get_teams_by_worker(worker_id):
        """Get all teams that a worker belongs to"""
        memberships = TeamMember.query.filter_by(worker_id=worker_id).all()
        team_ids = [m.team_id for m in memberships]
        return WorkerTeam.query.filter(WorkerTeam.id.in_(team_ids)).all() if team_ids else []
    
    @staticmethod
    def search_teams(search_term):
        """Search teams by name"""
        return WorkerTeam.query.filter(
            WorkerTeam.name.ilike(f'%{search_term}%')
        ).all()


class TeamMember(db.Model):
    __tablename__ = 'team_members'
    id = db.Column(db.String(20), primary_key=True)
    team_id = db.Column(db.String(20), db.ForeignKey('worker_teams.id', ondelete='CASCADE'), nullable=False)
    worker_id = db.Column(db.String(20), db.ForeignKey('workers.id', ondelete='CASCADE'), nullable=False)
    role_in_team = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # worker_ref is defined in worker.py - DO NOT define worker relationship here
    
    __table_args__ = (db.UniqueConstraint('team_id', 'worker_id', name='unique_team_member'),)
    
    def to_dict(self):
        # Get worker from worker_ref (defined in Worker model)
        worker = self.worker_ref if hasattr(self, 'worker_ref') else None
        
        return {
            'id': self.id,
            'teamId': self.team_id,
            'workerId': self.worker_id,
            'workerName': worker.name if worker else None,
            'worker': worker.to_dict() if worker else None,
            'roleInTeam': self.role_in_team,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def get_member_by_id(member_id):
        """Get a team member by ID"""
        return TeamMember.query.get(member_id)
    
    @staticmethod
    def get_members_by_team(team_id):
        """Get all members of a team"""
        return TeamMember.query.filter_by(team_id=team_id).all()
    
    @staticmethod
    def get_members_by_worker(worker_id):
        """Get all team memberships for a worker"""
        return TeamMember.query.filter_by(worker_id=worker_id).all()
    
    @staticmethod
    def get_team_member(team_id, worker_id):
        """Get a specific team member record"""
        return TeamMember.query.filter_by(team_id=team_id, worker_id=worker_id).first()
    
    @staticmethod
    def get_members_by_role(team_id, role):
        """Get all members of a team with a specific role"""
        return TeamMember.query.filter_by(team_id=team_id, role_in_team=role).all()