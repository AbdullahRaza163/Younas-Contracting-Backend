from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text  # IMPORTANT: Add this import
from datetime import datetime
import os
import json
import random
import string
from dotenv import load_dotenv
import psycopg2
from sqlalchemy.exc import SQLAlchemyError
import urllib.parse

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# ============================================
# DATABASE CONFIGURATION - POSTGRESQL
# ============================================

# Get database URL from environment variable
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/haji_younas_db')

# If password contains special characters, URL encode it
# The .env should already have URL encoded password, but just in case
try:
    # Parse the URL to check if password needs encoding
    from urllib.parse import urlparse, quote, unquote
    
    parsed = urlparse(DATABASE_URL)
    if parsed.password:
        # Check if password is already encoded
        decoded_password = unquote(parsed.password)
        if decoded_password != parsed.password:
            # Password is encoded, keep as is
            pass
        elif any(c in parsed.password for c in '!@#$%^&*()'):
            # Password has special chars, encode it
            encoded_password = quote(parsed.password, safe='')
            DATABASE_URL = f"{parsed.scheme}://{parsed.username}:{encoded_password}@{parsed.hostname}:{parsed.port}{parsed.path}"
            print("✅ Password encoded for database connection")
except Exception as e:
    print(f"⚠️ Could not parse DATABASE_URL: {e}")

# Configure PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
}
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Configure CORS properly - Allow all for development
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:3000", 
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
            "http://localhost:3002",
            "http://127.0.0.1:3002",
            "*"  # Allow all for development
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Accept"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

# Initialize database
db = SQLAlchemy(app)

# ============================================
# DATABASE MODELS
# ============================================

class Site(db.Model):
    __tablename__ = 'sites'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    manager = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    entries = db.relationship('Entry', backref='site', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'manager': self.manager,
            'phone': self.phone,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }

class Worker(db.Model):
    __tablename__ = 'workers'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50))
    daily_rate = db.Column(db.Float, default=0.0)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    attendance_records = db.relationship('Attendance', backref='worker', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'dailyRate': self.daily_rate,
            'phone': self.phone,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }

class Entry(db.Model):
    __tablename__ = 'entries'
    
    id = db.Column(db.String(20), primary_key=True)
    date = db.Column(db.Date, nullable=False)
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False)
    kamai = db.Column(db.Float, default=0.0)
    labour = db.Column(db.Float, default=0.0)
    overhead = db.Column(db.Float, default=0.0)
    one_time = db.Column(db.Float, default=0.0)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'siteId': self.site_id,
            'siteName': self.site.name if self.site else None,
            'kamai': self.kamai,
            'labour': self.labour,
            'overhead': self.overhead,
            'oneTime': self.one_time,
            'note': self.note,
            'createdAt': self.created_at.isoformat() if self.created_at else None
        }

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.String(20), primary_key=True)
    worker_id = db.Column(db.String(20), db.ForeignKey('workers.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    checked_in = db.Column(db.DateTime)
    checked_out = db.Column(db.DateTime)
    present = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'workerId': self.worker_id,
            'workerName': self.worker.name if self.worker else None,
            'date': self.date.isoformat() if self.date else None,
            'checkedIn': self.checked_in.isoformat() if self.checked_in else None,
            'checkedOut': self.checked_out.isoformat() if self.checked_out else None,
            'present': self.present,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }

class Setting(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        try:
            return {
                'key': self.key,
                'value': json.loads(self.value) if self.value else None
            }
        except:
            return {
                'key': self.key,
                'value': self.value
            }

# ============================================
# ROOT ROUTE
# ============================================

@app.route('/')
def index():
    return jsonify({
        'message': 'Haji Younas Contracting API',
        'status': 'running',
        'version': '1.0.0',
        'database': 'PostgreSQL',
        'endpoints': {
            'health': '/api/health',
            'sites': '/api/sites',
            'workers': '/api/workers',
            'entries': '/api/entries',
            'attendance': '/api/attendance',
            'settings': '/api/settings',
            'chat': '/api/chat'
        }
    })

# Helper function to generate ID
def generate_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))

# ============================================
# FIXED HEALTH CHECK - Using text()
# ============================================

@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health_check():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'OK'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
    
    try:
        # FIXED: Use text() for raw SQL
        db.session.execute(text('SELECT 1'))
        db_status = 'connected'
        db_details = 'PostgreSQL connection successful'
    except Exception as e:
        db_status = 'disconnected'
        db_details = str(e)
    
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.utcnow().isoformat(),
        'database': db_status,
        'database_details': db_details,
        'database_type': 'PostgreSQL',
        'server': 'Flask',
        'port': 5000,
        'cors_enabled': True
    })

# ============================================
# SITES ROUTES
# ============================================

@app.route('/api/sites', methods=['GET', 'OPTIONS'])
def get_sites():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'OK'})
        return response
    
    try:
        sites = Site.query.order_by(Site.created_at.desc()).all()
        return jsonify([s.to_dict() for s in sites])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sites', methods=['POST'])
def create_site():
    try:
        data = request.json
        site = Site(
            id=generate_id(),
            name=data.get('name'),
            location=data.get('location', ''),
            manager=data.get('manager', ''),
            phone=data.get('phone', '')
        )
        db.session.add(site)
        db.session.commit()
        return jsonify(site.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/sites/<site_id>', methods=['PUT'])
def update_site(site_id):
    try:
        site = Site.query.get_or_404(site_id)
        data = request.json
        site.name = data.get('name', site.name)
        site.location = data.get('location', site.location)
        site.manager = data.get('manager', site.manager)
        site.phone = data.get('phone', site.phone)
        db.session.commit()
        return jsonify(site.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/sites/<site_id>', methods=['DELETE'])
def delete_site(site_id):
    try:
        site = Site.query.get_or_404(site_id)
        db.session.delete(site)
        db.session.commit()
        return jsonify({'message': 'Site deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# WORKERS ROUTES
# ============================================

@app.route('/api/workers', methods=['GET'])
def get_workers():
    try:
        workers = Worker.query.order_by(Worker.created_at.desc()).all()
        return jsonify([w.to_dict() for w in workers])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workers', methods=['POST'])
def create_worker():
    try:
        data = request.json
        worker = Worker(
            id=generate_id(),
            name=data.get('name'),
            role=data.get('role', ''),
            daily_rate=float(data.get('dailyRate', 0)),
            phone=data.get('phone', '')
        )
        db.session.add(worker)
        db.session.commit()
        return jsonify(worker.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/workers/<worker_id>', methods=['PUT'])
def update_worker(worker_id):
    try:
        worker = Worker.query.get_or_404(worker_id)
        data = request.json
        worker.name = data.get('name', worker.name)
        worker.role = data.get('role', worker.role)
        worker.daily_rate = float(data.get('dailyRate', worker.daily_rate))
        worker.phone = data.get('phone', worker.phone)
        db.session.commit()
        return jsonify(worker.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/workers/<worker_id>', methods=['DELETE'])
def delete_worker(worker_id):
    try:
        worker = Worker.query.get_or_404(worker_id)
        db.session.delete(worker)
        db.session.commit()
        return jsonify({'message': 'Worker deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# ENTRIES ROUTES
# ============================================

@app.route('/api/entries', methods=['GET'])
def get_entries():
    try:
        # Get query parameters
        site_id = request.args.get('siteId')
        date_from = request.args.get('dateFrom')
        date_to = request.args.get('dateTo')
        
        query = Entry.query
        
        if site_id:
            query = query.filter_by(site_id=site_id)
        if date_from:
            query = query.filter(Entry.date >= date_from)
        if date_to:
            query = query.filter(Entry.date <= date_to)
        
        entries = query.order_by(Entry.date.desc()).all()
        return jsonify([e.to_dict() for e in entries])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/entries', methods=['POST'])
def create_entry():
    try:
        data = request.json
        
        # Get monthly overhead from settings
        setting = Setting.query.filter_by(key='monthly_overhead').first()
        monthly_overhead = float(setting.value) if setting else 194.0
        overhead = monthly_overhead / 30
        
        # Parse date
        entry_date = datetime.strptime(data.get('date'), '%Y-%m-%d').date()
        
        entry = Entry(
            id=generate_id(),
            date=entry_date,
            site_id=data.get('siteId'),
            kamai=float(data.get('kamai', 0)),
            labour=float(data.get('labour', 0)),
            overhead=float(overhead),
            one_time=float(data.get('oneTime', 0)),
            note=data.get('note', '')
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify(entry.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/entries/<entry_id>', methods=['PUT'])
def update_entry(entry_id):
    try:
        entry = Entry.query.get_or_404(entry_id)
        data = request.json
        
        if data.get('date'):
            entry.date = datetime.strptime(data.get('date'), '%Y-%m-%d').date()
        if data.get('siteId'):
            entry.site_id = data.get('siteId')
        if data.get('kamai') is not None:
            entry.kamai = float(data.get('kamai'))
        if data.get('labour') is not None:
            entry.labour = float(data.get('labour'))
        if data.get('oneTime') is not None:
            entry.one_time = float(data.get('oneTime'))
        if data.get('note') is not None:
            entry.note = data.get('note')
        
        db.session.commit()
        return jsonify(entry.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/entries/<entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    try:
        entry = Entry.query.get_or_404(entry_id)
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'message': 'Entry deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# ATTENDANCE ROUTES
# ============================================

@app.route('/api/attendance', methods=['GET'])
def get_attendance():
    try:
        worker_id = request.args.get('workerId')
        date = request.args.get('date')
        date_from = request.args.get('dateFrom')
        date_to = request.args.get('dateTo')
        
        query = Attendance.query
        
        if worker_id:
            query = query.filter_by(worker_id=worker_id)
        if date:
            query = query.filter_by(date=datetime.strptime(date, '%Y-%m-%d').date())
        if date_from:
            query = query.filter(Attendance.date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        if date_to:
            query = query.filter(Attendance.date <= datetime.strptime(date_to, '%Y-%m-%d').date())
        
        attendance = query.order_by(Attendance.date.desc()).all()
        return jsonify([a.to_dict() for a in attendance])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/attendance', methods=['POST'])
def create_or_update_attendance():
    try:
        data = request.json
        worker_id = data.get('workerId')
        date = datetime.strptime(data.get('date'), '%Y-%m-%d').date()
        checked_in = data.get('checkedIn')
        checked_out = data.get('checkedOut')
        present = data.get('present', False)
        
        # Parse timestamps if provided
        if checked_in:
            checked_in = datetime.fromisoformat(checked_in.replace('Z', '+00:00'))
        if checked_out:
            checked_out = datetime.fromisoformat(checked_out.replace('Z', '+00:00'))
        
        # Find existing record
        record = Attendance.query.filter_by(worker_id=worker_id, date=date).first()
        
        if record:
            # Update existing record
            if checked_in is not None:
                record.checked_in = checked_in
            if checked_out is not None:
                record.checked_out = checked_out
            if present is not None:
                record.present = present
            record.updated_at = datetime.utcnow()
        else:
            # Create new record
            record = Attendance(
                id=generate_id(),
                worker_id=worker_id,
                date=date,
                checked_in=checked_in,
                checked_out=checked_out,
                present=present or False
            )
            db.session.add(record)
        
        db.session.commit()
        return jsonify(record.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# SETTINGS ROUTES
# ============================================

@app.route('/api/settings', methods=['GET'])
def get_settings():
    try:
        settings = Setting.query.all()
        result = {}
        for s in settings:
            try:
                result[s.key] = json.loads(s.value)
            except:
                result[s.key] = s.value
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def update_settings():
    try:
        data = request.json
        
        for key, value in data.items():
            setting = Setting.query.filter_by(key=key).first()
            if setting:
                setting.value = json.dumps(value)
            else:
                setting = Setting(key=key, value=json.dumps(value))
                db.session.add(setting)
        
        db.session.commit()
        return jsonify({'message': 'Settings updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

# ============================================
# AI CHAT ENDPOINT
# ============================================

@app.route('/api/chat', methods=['POST'])
def chat():
    """Simple rule-based AI assistant"""
    try:
        data = request.json
        message = data.get('message', '').lower()
        
        # Calculate summary
        entries = Entry.query.all()
        total_kamai = sum(e.kamai for e in entries)
        total_labour = sum(e.labour for e in entries)
        total_overhead = sum(e.overhead for e in entries)
        total_onetime = sum(e.one_time for e in entries)
        net_profit = total_kamai - total_labour - total_overhead - total_onetime
        
        if 'profit' in message or 'balance' in message:
            reply = f"📊 Current Financial Summary:\n"
            reply += f"Total Revenue: {total_kamai:.3f} BD\n"
            reply += f"Total Labour: {total_labour:.3f} BD\n"
            reply += f"Total Overhead: {total_overhead:.3f} BD\n"
            reply += f"Total One-time: {total_onetime:.3f} BD\n"
            reply += f"Net Profit: {net_profit:.3f} BD"
            return jsonify({'reply': reply})
        
        elif 'site' in message:
            sites = Site.query.all()
            reply = "📍 Site Performance:\n"
            for site in sites:
                site_entries = Entry.query.filter_by(site_id=site.id).all()
                site_kamai = sum(e.kamai for e in site_entries)
                site_labour = sum(e.labour for e in site_entries)
                site_profit = site_kamai - site_labour
                reply += f"\n• {site.name}: {site_profit:.3f} BD"
            return jsonify({'reply': reply})
        
        elif 'worker' in message or 'employee' in message:
            workers = Worker.query.all()
            reply = "👷 Workers Summary:\n"
            for worker in workers:
                attendance = Attendance.query.filter_by(worker_id=worker.id).all()
                days_present = sum(1 for a in attendance if a.present)
                # Calculate total hours
                total_hours = 0
                for a in attendance:
                    if a.checked_in and a.checked_out:
                        try:
                            if isinstance(a.checked_in, str):
                                start = datetime.fromisoformat(a.checked_in.replace('Z', '+00:00'))
                                end = datetime.fromisoformat(a.checked_out.replace('Z', '+00:00'))
                            else:
                                start = a.checked_in
                                end = a.checked_out
                            total_hours += (end - start).total_seconds() / 3600
                        except:
                            pass
                reply += f"\n• {worker.name} ({worker.role}): {days_present} days, {total_hours:.1f} hours, {worker.daily_rate} BD/day"
            return jsonify({'reply': reply})
        
        else:
            reply = f"🤖 I'm your business assistant. I can tell you about:\n"
            reply += "• Profit & Balance\n"
            reply += "• Site Performance\n"
            reply += "• Worker Information\n"
            reply += "\nJust ask me a question!"
            return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================
# ADD CORS HEADERS MANUALLY (Fallback)
# ============================================

@app.after_request
def after_request(response):
    """Add CORS headers to every response"""
    origin = request.headers.get('Origin')
    if origin:
        response.headers.add('Access-Control-Allow-Origin', origin)
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# ============================================
# CLI COMMANDS
# ============================================

@app.cli.command('init-db')
def init_db_command():
    """Initialize the database"""
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Create default settings
            if not Setting.query.filter_by(key='monthly_overhead').first():
                setting = Setting(key='monthly_overhead', value=json.dumps(194.0))
                db.session.add(setting)
                db.session.commit()
                print("✅ Default settings created")
            
            print(f"✅ Database initialized successfully")
            print(f"📁 Database: PostgreSQL at {app.config['SQLALCHEMY_DATABASE_URI']}")
        except Exception as e:
            print(f"❌ Database error: {e}")

@app.cli.command('seed-test')
def seed_test():
    """Add test data"""
    from datetime import datetime, timedelta
    
    with app.app_context():
        try:
            # Check if data exists
            if Site.query.first():
                print("⚠️ Data already exists. Skipping seed.")
                return
            
            # Create sites
            sites = [
                Site(id='s1', name='Jasra Villa Al Hilal', location='Jasra', manager='Ahmed', phone='+973 1234 5678'),
                Site(id='s2', name='Seef Tower', location='Seef', manager='Khalid', phone='+973 8765 4321'),
                Site(id='s3', name='Amwaj Residence', location='Amwaj Islands', manager='Mohammed', phone='+973 2345 6789'),
            ]
            for site in sites:
                db.session.add(site)
            
            # Create workers
            workers = [
                Worker(id='w1', name='Ali', role='Mason', daily_rate=12.0, phone='+973 1111 1111'),
                Worker(id='w2', name='Rahim', role='Helper', daily_rate=8.0, phone='+973 2222 2222'),
                Worker(id='w3', name='Hassan', role='Supervisor', daily_rate=15.0, phone='+973 3333 3333'),
                Worker(id='w4', name='Ahmed', role='Electrician', daily_rate=14.0, phone='+973 4444 4444'),
                Worker(id='w5', name='Salman', role='Plumber', daily_rate=13.0, phone='+973 5555 5555'),
            ]
            for worker in workers:
                db.session.add(worker)
            
            # Create entries
            today = datetime.now()
            for i in range(30):
                date = (today - timedelta(days=i)).date()
                site = sites[i % len(sites)]
                entry = Entry(
                    id=generate_id(),
                    date=date,
                    site_id=site.id,
                    kamai=100 + i * 10,
                    labour=40 + i * 5,
                    overhead=6.47,
                    one_time=5 + i * 2,
                    note=f"Daily entry for {date}"
                )
                db.session.add(entry)
            
            db.session.commit()
            print("✅ Test data added successfully!")
            print(f"📊 Created {len(sites)} sites, {len(workers)} workers, and 30 entries")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error seeding data: {e}")

# ============================================
# RUN APP
# ============================================

if __name__ == '__main__':
    # Create tables if they don't exist
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Create default settings if not exists
            if not Setting.query.filter_by(key='monthly_overhead').first():
                setting = Setting(key='monthly_overhead', value=json.dumps(194.0))
                db.session.add(setting)
                db.session.commit()
                print("✅ Default settings created")
                
        except Exception as e:
            print(f"❌ Database error: {e}")
            print("📁 Please check your PostgreSQL connection settings.")
            print(f"📁 DATABASE_URL: {DATABASE_URL}")
    
    print("🚀 Starting Flask server...")
    print(f"📡 Server: http://127.0.0.1:5000")
    print(f"🔗 API Base: http://127.0.0.1:5000/api")
    print(f"📁 Database: PostgreSQL")
    app.run(debug=True, host='0.0.0.0', port=5000)