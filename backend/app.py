from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import json
import random
import string
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# ============================================
# DATABASE CONFIGURATION
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_PATH = os.path.join(BASE_DIR, 'instance')

# Create instance folder if it doesn't exist
if not os.path.exists(INSTANCE_PATH):
    os.makedirs(INSTANCE_PATH)

# Use absolute path for database
DB_PATH = os.path.join(INSTANCE_PATH, 'haji_younas.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Configure CORS properly
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://127.0.0.1:3000", "*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Initialize database
db = SQLAlchemy(app)

# ============================================
# ROOT ROUTE
# ============================================
@app.route('/')
def index():
    return jsonify({
        'message': 'Haji Younas Contracting API',
        'status': 'running',
        'version': '1.0.0',
        'database': DB_PATH,
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
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'manager': self.manager,
            'phone': self.phone
        }

class Worker(db.Model):
    __tablename__ = 'workers'
    
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50))
    daily_rate = db.Column(db.Float, default=0.0)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'dailyRate': self.daily_rate,
            'phone': self.phone
        }

class Entry(db.Model):
    __tablename__ = 'entries'
    
    id = db.Column(db.String(20), primary_key=True)
    date = db.Column(db.String(10), nullable=False)
    site_id = db.Column(db.String(20), db.ForeignKey('sites.id'), nullable=False)
    kamai = db.Column(db.Float, default=0.0)
    labour = db.Column(db.Float, default=0.0)
    overhead = db.Column(db.Float, default=0.0)
    one_time = db.Column(db.Float, default=0.0)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date,
            'siteId': self.site_id,
            'kamai': self.kamai,
            'labour': self.labour,
            'overhead': self.overhead,
            'oneTime': self.one_time,
            'note': self.note
        }

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.String(20), primary_key=True)
    worker_id = db.Column(db.String(20), db.ForeignKey('workers.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    checked_in = db.Column(db.String(50))  # ISO datetime string
    checked_out = db.Column(db.String(50))  # ISO datetime string
    present = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'workerId': self.worker_id,
            'date': self.date,
            'checkedIn': self.checked_in,
            'checkedOut': self.checked_out,
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
        return {
            'key': self.key,
            'value': json.loads(self.value) if self.value else None
        }

# ============================================
# API ROUTES
# ============================================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.utcnow().isoformat(),
        'database': 'connected' if db.engine else 'disconnected',
        'db_path': DB_PATH
    })

# Sites Routes
@app.route('/api/sites', methods=['GET'])
def get_sites():
    sites = Site.query.all()
    return jsonify([s.to_dict() for s in sites])

@app.route('/api/sites', methods=['POST'])
def create_site():
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

@app.route('/api/sites/<site_id>', methods=['PUT'])
def update_site(site_id):
    site = Site.query.get_or_404(site_id)
    data = request.json
    site.name = data.get('name', site.name)
    site.location = data.get('location', site.location)
    site.manager = data.get('manager', site.manager)
    site.phone = data.get('phone', site.phone)
    db.session.commit()
    return jsonify(site.to_dict())

@app.route('/api/sites/<site_id>', methods=['DELETE'])
def delete_site(site_id):
    site = Site.query.get_or_404(site_id)
    db.session.delete(site)
    db.session.commit()
    return jsonify({'message': 'Site deleted successfully'})

# Workers Routes
@app.route('/api/workers', methods=['GET'])
def get_workers():
    workers = Worker.query.all()
    return jsonify([w.to_dict() for w in workers])

@app.route('/api/workers', methods=['POST'])
def create_worker():
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

@app.route('/api/workers/<worker_id>', methods=['PUT'])
def update_worker(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    data = request.json
    worker.name = data.get('name', worker.name)
    worker.role = data.get('role', worker.role)
    worker.daily_rate = float(data.get('dailyRate', worker.daily_rate))
    worker.phone = data.get('phone', worker.phone)
    db.session.commit()
    return jsonify(worker.to_dict())

@app.route('/api/workers/<worker_id>', methods=['DELETE'])
def delete_worker(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    db.session.delete(worker)
    db.session.commit()
    return jsonify({'message': 'Worker deleted successfully'})

# Entries Routes
@app.route('/api/entries', methods=['GET'])
def get_entries():
    entries = Entry.query.order_by(Entry.date.desc()).all()
    return jsonify([e.to_dict() for e in entries])

@app.route('/api/entries', methods=['POST'])
def create_entry():
    data = request.json
    
    # Get monthly overhead from settings
    setting = Setting.query.filter_by(key='monthly_overhead').first()
    monthly_overhead = float(setting.value) if setting else 194.0
    overhead = monthly_overhead / 30
    
    entry = Entry(
        id=generate_id(),
        date=data.get('date'),
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

@app.route('/api/entries/<entry_id>', methods=['PUT'])
def update_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    data = request.json
    entry.date = data.get('date', entry.date)
    entry.site_id = data.get('siteId', entry.site_id)
    entry.kamai = float(data.get('kamai', entry.kamai))
    entry.labour = float(data.get('labour', entry.labour))
    entry.one_time = float(data.get('oneTime', entry.one_time))
    entry.note = data.get('note', entry.note)
    db.session.commit()
    return jsonify(entry.to_dict())

@app.route('/api/entries/<entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'message': 'Entry deleted successfully'})

# ============================================
# ATTENDANCE ROUTES - WITH CHECKED_IN/OUT
# ============================================
@app.route('/api/attendance', methods=['GET'])
def get_attendance():
    worker_id = request.args.get('workerId')
    date = request.args.get('date')
    
    query = Attendance.query
    if worker_id:
        query = query.filter_by(worker_id=worker_id)
    if date:
        query = query.filter_by(date=date)
    
    attendance = query.all()
    return jsonify([a.to_dict() for a in attendance])

@app.route('/api/attendance', methods=['POST'])
def create_or_update_attendance():
    data = request.json
    worker_id = data.get('workerId')
    date = data.get('date')
    checked_in = data.get('checkedIn')
    checked_out = data.get('checkedOut')
    present = data.get('present', False)
    
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

# Settings Routes
@app.route('/api/settings', methods=['GET'])
def get_settings():
    settings = Setting.query.all()
    result = {}
    for s in settings:
        try:
            result[s.key] = json.loads(s.value)
        except:
            result[s.key] = s.value
    return jsonify(result)

@app.route('/api/settings', methods=['POST'])
def update_settings():
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

# AI Chat endpoint
@app.route('/api/chat', methods=['POST'])
def chat():
    """Simple rule-based AI assistant"""
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
        reply = "👷 Workers:\n"
        for worker in workers:
            attendance = Attendance.query.filter_by(worker_id=worker.id).all()
            days_present = sum(1 for a in attendance if a.present)
            # Calculate total hours
            total_hours = 0
            for a in attendance:
                if a.checked_in and a.checked_out:
                    try:
                        start = datetime.fromisoformat(a.checked_in)
                        end = datetime.fromisoformat(a.checked_out)
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
        reply += "Just ask me a question!"
        return jsonify({'reply': reply})

# ============================================
# CLI COMMANDS
# ============================================

@app.cli.command('init-db')
def init_db_command():
    """Initialize the database"""
    with app.app_context():
        db.create_all()
        
        # Create default settings
        if not Setting.query.filter_by(key='monthly_overhead').first():
            setting = Setting(key='monthly_overhead', value=json.dumps(194.0))
            db.session.add(setting)
            db.session.commit()
        
        print("✅ Database initialized successfully")
        print(f"📁 Database location: {DB_PATH}")

@app.cli.command('seed-test')
def seed_test():
    """Add test data"""
    from datetime import datetime, timedelta
    
    with app.app_context():
        # Check if data exists
        if Site.query.first():
            print("⚠️ Data already exists. Skipping seed.")
            return
        
        # Create sites
        sites = [
            Site(id='s1', name='Jasra Villa Al Hilal', location='Jasra', manager='Ahmed'),
            Site(id='s2', name='Seef Tower', location='Seef', manager='Khalid'),
        ]
        for site in sites:
            db.session.add(site)
        
        # Create workers
        workers = [
            Worker(id='w1', name='Ali', role='Mason', daily_rate=12.0),
            Worker(id='w2', name='Rahim', role='Helper', daily_rate=8.0),
            Worker(id='w3', name='Hassan', role='Supervisor', daily_rate=15.0),
        ]
        for worker in workers:
            db.session.add(worker)
        
        # Create entries
        today = datetime.now()
        for i in range(5):
            date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            site_id = sites[i % len(sites)].id
            entry = Entry(
                id=generate_id(),
                date=date,
                site_id=site_id,
                kamai=100 + i * 10,
                labour=40 + i * 5,
                overhead=6.47,
                one_time=5 + i * 2,
                note=f"Daily entry for {date}"
            )
            db.session.add(entry)
        
        db.session.commit()
        print("✅ Test data added successfully!")

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
            print("📁 Please make sure the 'instance' folder exists and is writable.")
    
    print(f"🚀 Starting Flask server on http://127.0.0.1:5000")
    print(f"📁 Database: {DB_PATH}")
    # For Vercel deployment
    app = app  # Vercel looks for 'app' variable

    if __name__ == '__main__':
     app.run(debug=True, host='127.0.0.1', port=5000)