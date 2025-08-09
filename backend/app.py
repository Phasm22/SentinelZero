"""
New modular Flask application entry point
"""
import os
import sys
import threading
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

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
from src.services.whats_up import whats_up_monitor
from src.services.cleanup import scheduled_cleanup_job

# Import models to register them with SQLAlchemy
from src.models import Scan, Alert

# Global instances
db = None
socketio = None
scheduler = None

def create_app():
    """Application factory pattern"""
    global db, socketio, scheduler
    
    # Create Flask app
    app = Flask(__name__)
    
    # Enable CORS for all routes
    CORS(app, origins="*", supports_credentials=True)
    
    # Configuration
    app.config['SECRET_KEY'] = 'sentinelzero-dev-key-change-in-production'
    
    # Ensure instance directory exists
    instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    # Use absolute path for database
    db_path = os.path.join(instance_dir, 'sentinelzero.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db = init_db(app)
    socketio = SocketIO(app, cors_allowed_origins="*")
    scheduler = init_scheduler()
    try:
        # Run cleanup daily at 03:15 UTC (no lambda for serializable ref)
        scheduler.add_job(scheduled_cleanup_job, 'cron', hour=3, minute=15, id='xml_cleanup', replace_existing=True)
    except Exception as e:
        print(f'[WARN] Failed to schedule cleanup job: {e}')
    
    # Socket.IO event handlers
    @socketio.on('connect')
    def handle_connect():
        print(f'[SOCKET] Client connected')
        socketio.emit('scan_log', {'msg': 'Connected to SentinelZero'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        print(f'[SOCKET] Client disconnected')
    
    @socketio.on('ping')
    def handle_ping(data=None):
        print(f'[SOCKET] Ping received from client: {data}')
        socketio.emit('pong', {'message': 'Server received ping'})
    
    # Create database tables
    try:
        with app.app_context():
            # For development: Drop and recreate tables to ensure schema updates
            db.drop_all()
            db.create_all()
            print(f'[INFO] Database schema recreated at: {db_path}')
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
    
    # Legacy routes for compatibility with Vite proxy
    @app.route('/clear-all-data', methods=['POST'])
    def clear_all_data():
        """Legacy route to clear all scan data"""
        try:
            from src.models import Scan, Alert
            # Delete all scans and alerts
            scan_count = Scan.query.count()
            alert_count = Alert.query.count()
            Scan.query.delete()
            Alert.query.delete()
            db.session.commit()
            print(f'[DEBUG] Cleared {scan_count} scans and {alert_count} alerts.')
            return jsonify({'status': 'success', 'message': f'Cleared {scan_count} scans and {alert_count} alerts'})
        except Exception as e:
            db.session.rollback()
            print(f'[DEBUG] Error clearing all data: {e}')
            return jsonify({'status': 'error', 'message': f'Error clearing all data: {str(e)}'}), 500
    
    # Serve React static files in production
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        """Serve React app for non-API routes"""
        if path and (path.startswith('api/') or '.' in path):
            # Let API routes and static assets through
            return app.send_static_file(path) if '.' in path else ('Not Found', 404)
        
        # Check if running in development (React dev server handles routing)
        if os.environ.get('FLASK_ENV') == 'development':
            return ('Development mode: Use React dev server', 200)
        
        # Production: serve React build
        try:
            return send_from_directory('../frontend/react-sentinelzero/dist', 'index.html')
        except:
            return ('Frontend not built. Run: cd frontend/react-sentinelzero && npm run build', 500)
    
    # Start background services
    def start_background_services():
        """Start background monitoring services"""
        with app.app_context():
            print('[INFO] Starting What\'s Up monitoring...')
            threading.Thread(target=whats_up_monitor, args=(socketio, app), daemon=True).start()
    
    # Initialize background services after app is ready
    threading.Timer(2.0, start_background_services).start()
    
    return app

def main():
    """Main entry point"""
    app = create_app()
    
    # Development server
    if __name__ == '__main__':
        print('='*60)
        print('🛡️  SentinelZero Network Security Scanner')
        print('='*60)
        print('📡 Backend Server: http://0.0.0.0:5000 (accessible from any interface)')
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
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    main()
