# models/performance.py
from models import db
from datetime import datetime
import random
import string
from models.site import Site
from models.team import WorkerTeam
from models.worker import Worker

class PerformanceKPI(db.Model):
    """KPI Definitions"""
    __tablename__ = 'performance_kpis'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # 'productivity', 'financial', 'quality', 'safety'
    description = db.Column(db.Text)
    formula = db.Column(db.Text)
    target_value = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    metrics = db.relationship('PerformanceMetric', backref='kpi', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'formula': self.formula,
            'targetValue': self.target_value,
            'unit': self.unit,
            'isActive': self.is_active,
            'metricCount': self.metrics.count(),
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def get_by_category(category):
        return PerformanceKPI.query.filter_by(category=category, is_active=True).all()
    
    @staticmethod
    def get_active_kpis():
        return PerformanceKPI.query.filter_by(is_active=True).all()


class PerformanceMetric(db.Model):
    """Calculated Performance Metrics"""
    __tablename__ = 'performance_metrics'
    
    id = db.Column(db.String(20), primary_key=True)
    kpi_id = db.Column(db.String(20), db.ForeignKey('performance_kpis.id', ondelete='CASCADE'), nullable=False)
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='SET NULL'))
    team_id = db.Column(db.String(20), db.ForeignKey('worker_teams.id', ondelete='SET NULL'))
    worker_id = db.Column(db.String(20), db.ForeignKey('workers.id', ondelete='SET NULL'))
    period_type = db.Column(db.String(20), nullable=False)  # 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
    period_date = db.Column(db.Date, nullable=False)
    actual_value = db.Column(db.Float, default=0.0)
    target_value = db.Column(db.Float, default=0.0)
    variance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    site = db.relationship('Site', backref='performance_metrics')
    team = db.relationship('WorkerTeam', backref='performance_metrics')
    worker = db.relationship('Worker', backref='performance_metrics')
    
    def to_dict(self):
        return {
            'id': self.id,
            'kpiId': self.kpi_id,
            'kpiName': self.kpi.name if self.kpi else None,
            'kpiCategory': self.kpi.category if self.kpi else None,
            'siteId': self.site_id,
            'siteName': self.site.name if self.site else None,
            'teamId': self.team_id,
            'teamName': self.team.name if self.team else None,
            'workerId': self.worker_id,
            'workerName': self.worker.name if self.worker else None,
            'periodType': self.period_type,
            'periodDate': self.period_date.isoformat() if self.period_date else None,
            'actualValue': self.actual_value,
            'targetValue': self.target_value,
            'variance': self.variance,
            'performance': (self.actual_value / self.target_value * 100) if self.target_value > 0 else 0,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def calculate_variance(self):
        """Calculate variance between actual and target"""
        self.variance = self.actual_value - self.target_value
        return self.variance
    
    def calculate_performance(self):
        """Calculate performance percentage"""
        if self.target_value > 0:
            return (self.actual_value / self.target_value) * 100
        return 0
    
    @staticmethod
    def get_by_period(period_type, period_date):
        return PerformanceMetric.query.filter_by(
            period_type=period_type,
            period_date=period_date
        ).all()
    
    @staticmethod
    def get_by_site(site_id, period_type=None, period_date=None):
        query = PerformanceMetric.query.filter_by(site_id=site_id)
        if period_type:
            query = query.filter_by(period_type=period_type)
        if period_date:
            query = query.filter_by(period_date=period_date)
        return query.all()


class PerformanceRanking(db.Model):
    """Performance Rankings"""
    __tablename__ = 'performance_rankings'
    
    id = db.Column(db.String(20), primary_key=True)
    entity_type = db.Column(db.String(20), nullable=False)  # 'site', 'team', 'worker'
    entity_id = db.Column(db.String(20), nullable=False)
    metric_id = db.Column(db.String(20), nullable=False)
    period_type = db.Column(db.String(20), nullable=False)
    period_date = db.Column(db.Date, nullable=False)
    score = db.Column(db.Float, default=0.0)
    rank_position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'entityType': self.entity_type,
            'entityId': self.entity_id,
            'entityName': self._get_entity_name(),
            'metricId': self.metric_id,
            'periodType': self.period_type,
            'periodDate': self.period_date.isoformat() if self.period_date else None,
            'score': self.score,
            'rankPosition': self.rank_position,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }
    
    def _get_entity_name(self):
        """Get entity name based on type"""
        if self.entity_type == 'site':
            site = Site.query.get(self.entity_id)
            return site.name if site else 'Unknown'
        elif self.entity_type == 'team':
            team = WorkerTeam.query.get(self.entity_id)
            return team.name if team else 'Unknown'
        elif self.entity_type == 'worker':
            worker = Worker.query.get(self.entity_id)
            return worker.name if worker else 'Unknown'
        return 'Unknown'
    
    @staticmethod
    def get_rankings(entity_type, period_type, limit=10):
        return PerformanceRanking.query.filter_by(
            entity_type=entity_type,
            period_type=period_type
        ).order_by(PerformanceRanking.rank_position).limit(limit).all()