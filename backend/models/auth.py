# models/auth.py
from datetime import datetime, timedelta
import bcrypt
import jwt
import random
import string
import re
from config import Config


def generate_id():
    """Generate a short ID"""
    chars = string.ascii_lowercase + '0123456789'
    return ''.join(random.choice(chars) for _ in range(9))


# Define the models as standalone classes that will be bound to db later
# We'll use a class decorator pattern

class User:
    """User model - will be bound to db in __init__.py"""
    __tablename__ = 'users'
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def set_password(self, password):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def check_password(self, password):
        if not self.password_hash:
            return False
        try:
            return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        except Exception:
            return False
    
    def generate_access_token(self):
        payload = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'exp': datetime.utcnow() + Config.JWT_ACCESS_TOKEN_EXPIRES
        }
        return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')
    
    def generate_refresh_token(self):
        payload = {
            'id': self.id,
            'exp': datetime.utcnow() + Config.JWT_REFRESH_TOKEN_EXPIRES
        }
        return jwt.encode(payload, Config.JWT_REFRESH_SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def verify_access_token(token):
        try:
            payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
            return payload
        except:
            return None
    
    @staticmethod
    def verify_refresh_token(token):
        try:
            payload = jwt.decode(token, Config.JWT_REFRESH_SECRET_KEY, algorithms=['HS256'])
            return payload
        except:
            return None
    
    @staticmethod
    def validate_password(password):
        if len(password) < 6:
            return False, "Password must be at least 6 characters"
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        if not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        return True, ""
    
    @staticmethod
    def validate_email(email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<User {self.username}>'


class UserSession:
    """User session model - will be bound to db in __init__.py"""
    __tablename__ = 'user_sessions'
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, 'expires_at') or not self.expires_at:
            self.expires_at = datetime.utcnow() + Config.JWT_REFRESH_TOKEN_EXPIRES
    
    def is_expired(self):
        return self.expires_at < datetime.utcnow()
    
    def revoke(self):
        self.is_revoked = True
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_revoked': self.is_revoked,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<UserSession {self.id} user_id={self.user_id}>'


class PasswordReset:
    """Password reset token model - will be bound to db in __init__.py"""
    __tablename__ = 'password_resets'
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, 'expires_at') or not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(hours=1)
    
    def is_expired(self):
        return self.expires_at < datetime.utcnow()
    
    def mark_used(self):
        self.used = True
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'token': self.token,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'used': self.used,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<PasswordReset {self.id} user_id={self.user_id}>'


# ============================================
# Auth Helper Functions
# ============================================

class AuthHelper:
    """Helper class for authentication operations"""
    
    @staticmethod
    def create_user_session(user, refresh_token, ip_address=None, user_agent=None):
        """Create a new user session"""
        from models import db
        
        session = UserSession(
            id=generate_id(),
            user_id=user.id,
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.session.add(session)
        db.session.commit()
        return session
    
    @staticmethod
    def revoke_all_sessions(user_id):
        """Revoke all sessions for a user"""
        from models import db, UserSession
        
        sessions = UserSession.query.filter_by(user_id=user_id, is_revoked=False).all()
        for session in sessions:
            session.revoke()
        db.session.commit()
        return len(sessions)
    
    @staticmethod
    def revoke_session(refresh_token):
        """Revoke a specific session"""
        from models import db, UserSession
        
        session = UserSession.query.filter_by(refresh_token=refresh_token).first()
        if session:
            session.revoke()
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def get_user_sessions(user_id):
        """Get all sessions for a user"""
        from models import UserSession
        
        return UserSession.query.filter_by(user_id=user_id).order_by(UserSession.created_at.desc()).all()
    
    @staticmethod
    def get_active_sessions(user_id):
        """Get active (non-revoked) sessions for a user"""
        from models import UserSession
        
        return UserSession.query.filter_by(user_id=user_id, is_revoked=False).order_by(UserSession.created_at.desc()).all()
    
    @staticmethod
    def cleanup_expired_sessions():
        """Delete expired sessions"""
        from models import db, UserSession
        
        expired = UserSession.query.filter(UserSession.expires_at < datetime.utcnow()).all()
        for session in expired:
            db.session.delete(session)
        db.session.commit()
        return len(expired)
    
    @staticmethod
    def cleanup_used_reset_tokens():
        """Delete used reset tokens older than 7 days"""
        from models import db, PasswordReset
        
        cutoff = datetime.utcnow() - timedelta(days=7)
        used_tokens = PasswordReset.query.filter(
            PasswordReset.used == True,
            PasswordReset.created_at < cutoff
        ).all()
        for token in used_tokens:
            db.session.delete(token)
        db.session.commit()
        return len(used_tokens)


# ============================================
# Auth Decorators
# ============================================

def authenticate_token():
    """Decorator to authenticate JWT token"""
    from functools import wraps
    from flask import request, jsonify
    from models import User
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Access token required'}), 401
            
            token = auth_header.split(' ')[1]
            payload = User.verify_access_token(token)
            
            if not payload:
                return jsonify({'error': 'Invalid or expired token'}), 403
            
            # Get user from database
            user = User.query.get(payload['id'])
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            if not user.is_active:
                return jsonify({'error': 'Account is deactivated'}), 401
            
            # Store user in request context
            request.user = user
            request.user_payload = payload
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_role(roles):
    """Decorator to require specific role"""
    from functools import wraps
    from flask import request, jsonify
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(request, 'user'):
                return jsonify({'error': 'Authentication required'}), 401
            
            user = request.user
            if user.role not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_admin():
    """Decorator to require admin role"""
    return require_role(['admin'])


def require_manager():
    """Decorator to require manager or admin role"""
    return require_role(['admin', 'manager'])