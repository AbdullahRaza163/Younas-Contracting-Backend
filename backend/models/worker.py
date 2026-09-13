# models/worker.py
from models import db
from datetime import datetime

class Worker(db.Model):
    __tablename__ = 'workers'
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50))
    daily_rate = db.Column(db.Float, default=0.0)
    hourly_rate = db.Column(db.Float, default=0.0)
    phone = db.Column(db.String(20))
    cpr = db.Column(db.String(20))
    join_date = db.Column(db.Date)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - Use unique backref names to avoid conflicts
    # Changed backref to 'supervisor_ref' to avoid conflict with WorkerTeam.supervisor
    supervised_teams = db.relationship('WorkerTeam', backref='supervisor_ref', lazy='dynamic', foreign_keys='WorkerTeam.supervisor_id')
    # Changed backref to 'worker_ref' to avoid conflict
    team_memberships = db.relationship('TeamMember', backref='worker_ref', lazy='dynamic', cascade='all, delete-orphan')
    # Attendance relationship
    attendances = db.relationship('Attendance', backref='worker_ref', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'dailyRate': self.daily_rate,
            'hourlyRate': self.hourly_rate,
            'phone': self.phone,
            'cpr': self.cpr,
            'joinDate': self.join_date.isoformat() if self.join_date else None,
            'active': self.active,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def to_dict_with_teams(self):
        data = self.to_dict()
        data['teams'] = [t.to_dict() for t in self.team_memberships.all()] if self.team_memberships else []
        data['supervisedTeams'] = [t.to_dict() for t in self.supervised_teams.all()] if self.supervised_teams else []
        return data
    
    def get_supervised_teams(self):
        """Get teams where this worker is the supervisor"""
        from .team import WorkerTeam
        return WorkerTeam.query.filter_by(supervisor_id=self.id).all()
    
    def get_team_memberships(self):
        """Get all team memberships for this worker"""
        from .team import TeamMember
        return TeamMember.query.filter_by(worker_id=self.id).all()
    
    def get_teams(self):
        """Get all teams this worker belongs to"""
        from .team import WorkerTeam, TeamMember
        memberships = TeamMember.query.filter_by(worker_id=self.id).all()
        team_ids = [m.team_id for m in memberships]
        return WorkerTeam.query.filter(WorkerTeam.id.in_(team_ids)).all() if team_ids else []
    
    def get_attendance_for_date(self, date):
        """Get attendance for this worker on a specific date"""
        from .attendance import Attendance
        return Attendance.query.filter_by(worker_id=self.id, date=date).first()
    
    def get_attendance_for_date_range(self, start_date, end_date):
        """Get attendance for this worker over a date range"""
        from .attendance import Attendance
        return Attendance.query.filter(
            Attendance.worker_id == self.id,
            Attendance.date >= start_date,
            Attendance.date <= end_date
        ).all()
    
    def get_attendance_summary(self, start_date, end_date):
        """Get attendance summary for this worker over a date range"""
        records = self.get_attendance_for_date_range(start_date, end_date)
        
        total_days = (end_date - start_date).days + 1
        total_present = sum(1 for r in records if r.present)
        total_hours = sum(r.total_hours or 0 for r in records)
        total_wages = sum(r.wage_earned or 0 for r in records)
        total_overtime = sum(r.overtime_hours or 0 for r in records)
        
        return {
            'worker_id': self.id,
            'worker_name': self.name,
            'total_days': total_days,
            'total_present': total_present,
            'total_absent': total_days - total_present,
            'total_hours': total_hours,
            'total_wages': total_wages,
            'total_overtime': total_overtime,
            'attendance_rate': (total_present / total_days * 100) if total_days > 0 else 0,
            'records': [r.to_dict() for r in records]
        }
    
    def calculate_wage(self, hours_worked, overtime_hours=0):
        """Calculate wage based on hourly rate and hours worked"""
        normal_wage = hours_worked * self.hourly_rate
        overtime_wage = overtime_hours * self.hourly_rate * 1.5
        return normal_wage + overtime_wage
    
    def is_in_team(self, team_id):
        """Check if worker is in a specific team"""
        from .team import TeamMember
        return TeamMember.query.filter_by(worker_id=self.id, team_id=team_id).first() is not None
    
    @staticmethod
    def get_active_workers():
        """Get all active workers"""
        return Worker.query.filter_by(active=True).all()
    
    @staticmethod
    def get_workers_by_role(role):
        """Get all workers with a specific role"""
        return Worker.query.filter_by(role=role, active=True).all()
    
    @staticmethod
    def get_worker_by_id(worker_id):
        """Get a worker by ID"""
        return Worker.query.get(worker_id)
    
    @staticmethod
    def search_workers(search_term):
        """Search workers by name or role"""
        return Worker.query.filter(
            db.or_(
                Worker.name.ilike(f'%{search_term}%'),
                Worker.role.ilike(f'%{search_term}%')
            )
        ).all()
    
    @staticmethod
    def get_workers_without_team():
        """Get all workers who are not in any team"""
        from .team import TeamMember
        # Get all worker IDs that are in teams
        team_worker_ids = db.session.query(TeamMember.worker_id).distinct().all()
        team_worker_ids = [id[0] for id in team_worker_ids]
        
        if team_worker_ids:
            return Worker.query.filter(~Worker.id.in_(team_worker_ids), Worker.active == True).all()
        return Worker.query.filter_by(active=True).all()
    
    @staticmethod
    def get_workers_by_team(team_id):
        """Get all workers in a specific team"""
        from .team import TeamMember
        members = TeamMember.query.filter_by(team_id=team_id).all()
        worker_ids = [m.worker_id for m in members]
        return Worker.query.filter(Worker.id.in_(worker_ids)).all() if worker_ids else []