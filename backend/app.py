from flask import Flask, jsonify, request
from flask_cors import CORS
from config import Config
from models import db
# Remove the handle_options import
# from utils.cors import handle_options
from routes import (
    sites_bp, workers_bp, teams_bp, entries_bp, 
    attendance_bp, expenses_bp, invoices_bp, items_bp,
    overhead_bp, cumulative_bp, summary_bp, settings_bp,projects_bp,clients_bp, equipment_bp,qc_bp, performance_bp,
    leave_bp,inventory_bp, loans_bp, advances_bp  , auth_bp  
)
from sqlalchemy import text

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)

# ====== SINGLE CORS CONFIGURATION ======
# Use ONLY flask-cors - no custom handlers
CORS(app, 
     origins=Config.CORS_ORIGINS,
     methods=Config.CORS_METHODS,
     allow_headers=Config.CORS_HEADERS,
     expose_headers=Config.CORS_EXPOSE_HEADERS,
     supports_credentials=True,
     max_age=86400)

# DO NOT call handle_options(app) - it would add duplicate headers
# handle_options(app)  # <-- REMOVED/COMMENTED OUT

# Register blueprints
app.register_blueprint(sites_bp)
app.register_blueprint(workers_bp)
app.register_blueprint(teams_bp)
app.register_blueprint(entries_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(expenses_bp)
app.register_blueprint(invoices_bp)
app.register_blueprint(items_bp)
app.register_blueprint(overhead_bp)
app.register_blueprint(cumulative_bp)
app.register_blueprint(summary_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(projects_bp) 
app.register_blueprint(clients_bp)
app.register_blueprint(equipment_bp)
app.register_blueprint(qc_bp)
app.register_blueprint(performance_bp)
app.register_blueprint(leave_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(loans_bp)
app.register_blueprint(advances_bp)
app.register_blueprint(auth_bp) 
# app.register_blueprint(dashboard_bp)
# Health check routes
@app.route('/')
def index():
    return jsonify({
        'message': 'Haji Younas Contracting API',
        'status': 'running',
        'version': '3.0.0'
    })

@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health_check():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'OK'})
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({'status': 'OK', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'error', 'database': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': str(error)}), 500

# Create tables and default data
with app.app_context():
    from models import Setting, Site
    from utils.helpers import generate_id
    
    try:
        db.create_all()
        print("✅ Database tables verified")
        
        default_settings = [
            ('monthly_overhead', '194.0', 'financial'),
            ('vat_rate', '0', 'financial'),
            ('working_hours_per_day', '8', 'attendance'),
            ('company_name', 'Haji Younas Contracting', 'company'),
            ('company_cr', '141997-1', 'company'),
            ('company_address', 'Flat/Shop 21, Bldg A0365, Road 55, Block 210, Muharraq', 'company'),
            ('company_phone', '+973 37099957', 'company'),
            ('company_email', 'hajiyounas.contracting@gmail.com', 'company')
        ]
        
        for key, value, category in default_settings:
            if not Setting.query.filter_by(key=key).first():
                setting = Setting(key=key, value=value, category=category)
                db.session.add(setting)
        
        db.session.commit()
        print("✅ Default settings verified")
            
    except Exception as e:
        print(f"❌ Database error: {e}")
        print(f"📁 DATABASE_URL: {app.config['SQLALCHEMY_DATABASE_URI']}")

if __name__ == '__main__':
    print("🚀 Starting Flask server...")
    print(f"📡 Server: http://127.0.0.1:5000")
    print(f"🔗 API Base: http://127.0.0.1:5000/api")
    print(f"📁 Database: PostgreSQL")
    print("🔄 CORS enabled for allowed origins")
    # In app.py, after registering blueprints
    print("✅ Registered blueprints:")
    print(f"  - sites_bp: {sites_bp.url_prefix}")
    print(f"  - workers_bp: {workers_bp.url_prefix}")
    print(f"  - entries_bp: {entries_bp.url_prefix}")
    print(f"  - attendance_bp: {attendance_bp.url_prefix}")
    print(f"  - expenses_bp: {expenses_bp.url_prefix}")
    print(f"  - invoices_bp: {invoices_bp.url_prefix}")
    print(f"  - items_bp: {items_bp.url_prefix}")
    print(f"  - overhead_bp: {overhead_bp.url_prefix}")
    print(f"  - cumulative_bp: {cumulative_bp.url_prefix}")  # Make sure this prints
    print(f"  - summary_bp: {summary_bp.url_prefix}")
    print(f"  - settings_bp: {settings_bp.url_prefix}")
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)