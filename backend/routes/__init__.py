# routes/__init__.py
from flask import Blueprint

# Create blueprint instances
sites_bp = Blueprint('sites', __name__, url_prefix='/api/sites')
workers_bp = Blueprint('workers', __name__, url_prefix='/api/workers')
teams_bp = Blueprint('teams', __name__, url_prefix='/api/teams')
entries_bp = Blueprint('entries', __name__, url_prefix='/api/entries')
attendance_bp = Blueprint('attendance', __name__, url_prefix='/api/attendance')
expenses_bp = Blueprint('expenses', __name__, url_prefix='/api/expenses')
invoices_bp = Blueprint('invoices', __name__, url_prefix='/api/invoices')
items_bp = Blueprint('items', __name__, url_prefix='/api/items')
overhead_bp = Blueprint('overhead', __name__, url_prefix='/api')
cumulative_bp = Blueprint('cumulative', __name__, url_prefix='/api/cumulative-tracker')
summary_bp = Blueprint('summary', __name__, url_prefix='/api/monthly-summary')
settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')
projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')
budget_bp = Blueprint('budget', __name__, url_prefix='/api/budget')
clients_bp = Blueprint('clients', __name__, url_prefix='/api/clients') 
equipment_bp = Blueprint('equipment', __name__, url_prefix='/api/equipment')
qc_bp = Blueprint('qc', __name__, url_prefix='/api/qc')
performance_bp = Blueprint('performance', __name__, url_prefix='/api/performance')
leave_bp = Blueprint('leave', __name__, url_prefix='/api/leave')
inventory_bp = Blueprint('inventory', __name__, url_prefix='/api/inventory')
loans_bp = Blueprint('loans', __name__, url_prefix='/api/loans')
advances_bp = Blueprint('advances', __name__, url_prefix='/api/advances')  # ← ADD THIS
auth_bp = Blueprint('auth', __name__, url_prefix='/api')
# dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')
# Import routes
from routes import (
    sites, workers, teams, entries, attendance, expenses, invoices, items,
    overhead, cumulative, monthly_summary, settings, projects, budget_forecast,
    clients, equipment, quality_control, performance, leave, inventory, loans,
    advances, auth  # ← ADD THIS
)