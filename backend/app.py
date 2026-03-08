"""Modular Flask application entry point."""
import os
import sys
import threading
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, send_from_directory, jsonify, request, g
from flask_socketio import SocketIO
from flask_cors import CORS

# Import our modular components
from src.config.database import init_db
from src.config.scheduler import init_scheduler
from src.routes.scan_routes import create_scan_blueprint
from src.routes.settings_routes import create_settings_blueprint
from src.routes.schedule_routes import create_schedule_blueprint
from src.routes.api_routes import create_api_blueprint
from src.routes.upload_routes import create_upload_blueprint
from src.routes.whatsup_routes import bp as whatsup_bp
from src.routes.insights_routes import insights_bp
from src.routes.diff_routes import diff_bp
from src.services.whats_up import whats_up_monitor
from src.services.whats_up import get_monitor as get_whats_up_monitor
from src.services.cleanup import scheduled_cleanup_job
from src.services.scan_runtime import ScanRuntime, register_socket_handlers
from src.services.observability import configure_logging, ensure_request_id, log_event

# Import models to register them with SQLAlchemy
from src.models import Scan, Alert

# Global instances
db = None
socketio = None
scheduler = None

def _resolve_allowed_origins(app):
    configured = app.config.get('CORS_ORIGINS')
    if configured:
        return configured

    env_origins = os.environ.get('SENTINEL_ALLOWED_ORIGINS')
    if env_origins:
        raw_values = [value.strip() for value in env_origins.split(',') if value.strip()]
        if any(value == '*' for value in raw_values):
            return '*'
        if raw_values:
            return raw_values

    if app.config.get('TESTING'):
        return ['http://localhost']

    return [
        'http://localhost:3173',
        'http://127.0.0.1:3173',
        'http://localhost:5000',
        'http://127.0.0.1:5000',
        'http://sentinelzero.prox:3173',
        'http://sentinelzero.prox:5000',
        'http://sentinelzero.prox',
        'https://sentinelzero.prox',
    ]

def _ensure_database_schema(app, db):
    """Create tables and add runtime columns when opening an older SQLite DB."""
    with app.app_context():
        db.create_all()

        engine = db.engine
        if not engine.url.drivername.startswith('sqlite'):
            return

        required_columns = {
            'status_message': "TEXT DEFAULT 'Pending'",
            'execution_mode': "VARCHAR(32) DEFAULT 'normal'",
            'error_code': "VARCHAR(64)",
            'error_detail': 'TEXT',
            'source': "VARCHAR(32) DEFAULT 'manual'",
            'initiated_by': "VARCHAR(64) DEFAULT 'api'",
            'correlation_id': "VARCHAR(64)",
        }

        table_name = Scan.__table__.name
        with engine.begin() as connection:
            existing = {
                row[1]
                for row in connection.exec_driver_sql(f'PRAGMA table_info({table_name})').fetchall()
            }
            for column_name, ddl in required_columns.items():
                if column_name not in existing:
                    connection.exec_driver_sql(
                        f'ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}'
                    )

def create_app(test_config=None):
    """Application factory pattern."""
    global db, socketio, scheduler

    # Create Flask app
    app = Flask(__name__)

    app.config.update({
        'SECRET_KEY': os.environ.get('SECRET_KEY', 'sentinelzero-dev-key-change-in-production'),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'ENABLE_BACKGROUND_SERVICES': True,
        'CORS_ORIGINS': None,
    })

    if os.environ.get('PYTEST_VERSION') or os.environ.get('PYTEST_CURRENT_TEST'):
        app.config['ENABLE_BACKGROUND_SERVICES'] = False
        app.config['TESTING'] = True

    if test_config:
        app.config.update(test_config)

    # Ensure instance directory exists
    instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    os.makedirs(instance_dir, exist_ok=True)

    # Use absolute path for database unless tests override it
    default_db_path = os.path.join(instance_dir, 'sentinelzero.db')
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', f'sqlite:///{default_db_path}')

    allowed_origins = _resolve_allowed_origins(app)
    CORS(
        app,
        origins=allowed_origins,
        supports_credentials=False,
        allow_headers=['Content-Type', 'Authorization'],
    )

    # Add CORS headers manually for Socket.IO preflight requests
    @app.before_request
    def before_request_logging():
        ensure_request_id()
        request._sentinel_started_at = time.monotonic()

    @app.after_request
    def after_request(response):
        origin = request.headers.get('Origin')
        if origin and (allowed_origins == '*' or origin in allowed_origins):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
        request_id = getattr(g, 'request_id', None)
        if request_id:
            response.headers['X-Request-ID'] = request_id
        started_at = getattr(request, '_sentinel_started_at', None)
        if started_at is not None:
            duration_ms = round((time.monotonic() - started_at) * 1000, 2)
            log_event(
                'http.request.completed',
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
        return response

    # Initialize extensions
    db = init_db(app)
    socketio = SocketIO(
        app,
        cors_allowed_origins=allowed_origins,
        async_mode='eventlet',
        logger=not app.config.get('TESTING', False),
        engineio_logger=True,
        allow_upgrades=True,
        ping_timeout=60,
        ping_interval=25,
    )
    runtime = ScanRuntime(db, socketio)
    app.extensions['scan_runtime'] = runtime
    register_socket_handlers(socketio, runtime)
    app.extensions['whats_up_monitor'] = get_whats_up_monitor()

    scheduler = init_scheduler() if not app.config.get('TESTING') else None
    try:
        if scheduler:
            scheduler.add_job(
                scheduled_cleanup_job,
                'cron',
                hour=3,
                minute=15,
                id='xml_cleanup',
                replace_existing=True,
            )
    except Exception as e:
        print(f'[WARN] Failed to schedule cleanup job: {e}')

    # Handle OPTIONS requests for CORS preflight
    @app.route('/socket.io/', methods=['OPTIONS'])
    @app.route('/socket.io/<path:path>', methods=['OPTIONS'])
    def socketio_options(path=''):
        """Handle CORS preflight for Socket.IO"""
        response = jsonify({'status': 'ok'})
        origin = request.headers.get('Origin')
        if origin and (allowed_origins == '*' or origin in allowed_origins):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        return response

    # Create database tables
    try:
        _ensure_database_schema(app, db)
        print(f"[INFO] Database tables ensured at: {app.config['SQLALCHEMY_DATABASE_URI']}")
    except Exception as e:
        print(f'[ERROR] Failed to initialize database: {e}')
        raise

    # Register blueprints
    app.register_blueprint(create_scan_blueprint(db, socketio), url_prefix='/api')
    app.register_blueprint(create_settings_blueprint(db), url_prefix='/api')
    app.register_blueprint(create_schedule_blueprint(db, socketio, scheduler), url_prefix='/api')
    app.register_blueprint(create_api_blueprint(db), url_prefix='/api')
    app.register_blueprint(create_upload_blueprint(db, socketio), url_prefix='/api')
    app.register_blueprint(whatsup_bp)
    app.register_blueprint(insights_bp, url_prefix='/')  # insights_bp already has /api in routes
    app.register_blueprint(diff_bp, url_prefix='/')      # /api/scan-diff/<id>

    
    # Legacy routes for compatibility with Vite proxy
    @app.route('/clear-all-data', methods=['POST'])
    def clear_all_data():
        """Legacy route to clear all scan data"""
        try:
            from src.services.data_management import delete_data
            summary = delete_data(
                db,
                scope='all',
                delete_files=True,
                prune_orphan_files=True,
            )
            return jsonify({'status': 'success', 'message': 'Data reset complete', 'summary': summary})
        except Exception as e:
            db.session.rollback()
            print(f'[DEBUG] Error clearing all data: {e}')
            return jsonify({'status': 'error', 'message': f'Error clearing all data: {str(e)}'}), 500
    
    # Serve React static files in production
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        """Serve React app for non-API routes"""
        if path == 'healthz':
            return {'status': 'ok'}, 200
        if path and (path.startswith('api/') or '.' in path):
            # Serve static assets from dist directory
            try:
                return send_from_directory('../frontend/react-sentinelzero/dist', path)
            except:
                return ('Not Found', 404)
        
        # Check if running in development (React dev server handles routing)
        if os.environ.get('FLASK_ENV') == 'development':
            return ('Development mode: Use React dev server', 200)
        
        # Production: serve React build
        try:
            return send_from_directory('../frontend/react-sentinelzero/dist', 'index.html')
        except:
            return ('Frontend not built. Run: cd frontend/react-sentinelzero && npm run build', 500)
    
    # Startup cleanup function
    def startup_cleanup():
        """Clean up any orphaned scans and processes on startup"""
        with app.app_context():
            print('[INFO] Performing startup cleanup...')
            
            try:
                # Cancel any scans that were marked as running when app was shut down
                running_scans = Scan.query.filter(Scan.status.in_(['running', 'parsing', 'saving', 'postprocessing'])).all()
                if running_scans:
                    print(f'[CLEANUP] Found {len(running_scans)} orphaned scans, marking as cancelled')
                    for scan in running_scans:
                        scan.status = 'cancelled'
                    db.session.commit()
                    print('[CLEANUP] Orphaned scans marked as cancelled')
            except Exception as e:
                print(f'[CLEANUP] Error during database cleanup (likely test environment): {e}')
            
            # Kill any orphaned nmap processes
            import subprocess
            try:
                # Find and kill any nmap processes that might be orphaned
                result = subprocess.run(['pgrep', '-f', 'nmap'], capture_output=True, text=True)
                if result.stdout.strip():
                    nmap_pids = result.stdout.strip().split('\n')
                    print(f'[CLEANUP] Found {len(nmap_pids)} nmap processes, killing orphaned ones')
                    for pid in nmap_pids:
                        try:
                            subprocess.run(['kill', '-9', pid], check=False)
                        except:
                            pass
                    print('[CLEANUP] Orphaned nmap processes killed')
            except Exception as e:
                print(f'[WARN] Could not clean up nmap processes: {e}')
            
            print('[INFO] Startup cleanup completed')
    
    # Start background services
    def start_background_services():
        """Start background monitoring services"""
        with app.app_context():
            print('[INFO] Starting What\'s Up monitoring...')
            threading.Thread(target=whats_up_monitor, args=(socketio, app), daemon=True).start()
    
    # Initialize background services after app is ready
    if app.config.get('ENABLE_BACKGROUND_SERVICES') and not app.config.get('TESTING'):
        threading.Timer(1.0, startup_cleanup).start()  # Cleanup first
        threading.Timer(2.0, start_background_services).start()

    return app

def main():
    """Main entry point"""
    app = create_app()
    bind_host = os.environ.get('SENTINEL_BIND_HOST', '0.0.0.0')
    bind_port_raw = os.environ.get('SENTINEL_BIND_PORT', '5000')
    try:
        bind_port = int(bind_port_raw)
    except (TypeError, ValueError):
        bind_port = 5000
    
    # Development server
    if __name__ == '__main__':
        print('='*60)
        print('🛡️  SentinelZero Network Security Scanner')
        print('='*60)
        print(f'📡 Backend Server: http://{bind_host}:{bind_port} (configured bind)')
        print('🌐 Frontend (dev): http://localhost:3173 or http://sentinelzero.prox:3173') 
        print('📊 Dashboard: http://localhost:3173/dashboard')
        print('⚙️  Settings: http://localhost:3173/settings')
        print('='*60)
        print('🔍 Starting scan engine...')
        print('📡 Initializing network monitoring...')
        print('🚀 Server ready!')
        print('='*60)
        
        # Disable debug mode completely to prevent multiple processes
        # This fixes socket connection conflicts caused by Flask's reloader
        print('🔧 Running in production mode to prevent multiple processes')
        print('🔧 Debug mode disabled for stable socket connections')
        
        # Run with SocketIO - debug=False prevents reloader
        socketio.run(app, host=bind_host, port=bind_port, debug=False, allow_unsafe_werkzeug=True)

# Create app instance for gunicorn
app = create_app()

if __name__ == '__main__':
    main()
    configure_logging()
