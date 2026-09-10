# routes/auth.py
from flask import request, jsonify
from datetime import datetime, timedelta
from models import db, User, UserSession, PasswordReset, generate_id
import re
from config import Config
from routes import auth_bp  # Import from routes __init__

# ============================================
# Helper Functions
# ============================================

def validate_password(password):
    """Validate password strength"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    return True, ""

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def create_tokens(user):
    """Create access and refresh tokens for user"""
    access_token = user.generate_access_token()
    refresh_token = user.generate_refresh_token()
    
    # Store refresh token in session
    session = UserSession(
        id=generate_id(),
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=7),
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    db.session.add(session)
    db.session.commit()
    
    return access_token, refresh_token

def revoke_all_sessions(user_id):
    """Revoke all sessions for a user"""
    sessions = UserSession.query.filter_by(user_id=user_id, is_revoked=False).all()
    for session in sessions:
        session.is_revoked = True
    db.session.commit()

# ============================================
# Authentication Routes
# ============================================

@auth_bp.route('/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'full_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        username = data['username'].strip()
        email = data['email'].strip().lower()
        password = data['password']
        full_name = data['full_name'].strip()
        role = data.get('role', 'user')
        
        # Validate email
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Validate password
        is_valid, error_msg = validate_password(password)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        # Create user
        user = User(
            id=generate_id(),
            username=username,
            email=email,
            full_name=full_name,
            role=role
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Generate tokens
        access_token, refresh_token = create_tokens(user)
        
        return jsonify({
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/auth/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        
        identifier = data.get('identifier', '').strip()
        password = data.get('password', '')
        
        if not identifier or not password:
            return jsonify({'error': 'Username/email and password are required'}), 400
        
        # Find user by username or email
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier.lower())
        ).first()
        
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 401
        
        if not user.check_password(password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Generate tokens
        access_token, refresh_token = create_tokens(user)
        
        return jsonify({
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/auth/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token using refresh token"""
    try:
        data = request.get_json()
        refresh_token = data.get('refresh_token')
        
        if not refresh_token:
            return jsonify({'error': 'Refresh token required'}), 400
        
        # Verify refresh token
        payload = User.verify_refresh_token(refresh_token)
        if not payload:
            return jsonify({'error': 'Invalid or expired refresh token'}), 401
        
        # Check if token exists and is not revoked
        session = UserSession.query.filter_by(
            refresh_token=refresh_token,
            is_revoked=False
        ).first()
        
        if not session:
            return jsonify({'error': 'Invalid refresh token'}), 401
        
        if session.expires_at < datetime.utcnow():
            return jsonify({'error': 'Refresh token expired'}), 401
        
        # Get user
        user = User.query.get(session.user_id)
        if not user or not user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 401
        
        # Revoke old refresh token
        session.is_revoked = True
        db.session.commit()
        
        # Generate new tokens
        access_token, new_refresh_token = create_tokens(user)
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': new_refresh_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/auth/logout', methods=['POST'])
def logout():
    """Logout user - revoke refresh token"""
    try:
        data = request.get_json()
        refresh_token = data.get('refresh_token')
        
        if refresh_token:
            session = UserSession.query.filter_by(refresh_token=refresh_token).first()
            if session:
                session.is_revoked = True
                db.session.commit()
        
        return jsonify({'message': 'Logged out successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/auth/me', methods=['GET'])
def get_current_user():
    """Get current user from access token"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Access token required'}), 401
        
        token = auth_header.split(' ')[1]
        payload = User.verify_access_token(token)
        
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 403
        
        user = User.query.get(payload['id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'user': user.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/auth/change-password', methods=['POST'])
def change_password():
    """Change user password"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Access token required'}), 401
        
        token = auth_header.split(' ')[1]
        payload = User.verify_access_token(token)
        
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 403
        
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({'error': 'Current and new password are required'}), 400
        
        # Validate new password
        is_valid, error_msg = validate_password(new_password)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        user = User.query.get(payload['id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        user.set_password(new_password)
        db.session.commit()
        
        # Revoke all sessions (force re-login)
        revoke_all_sessions(user.id)
        
        return jsonify({'message': 'Password updated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500