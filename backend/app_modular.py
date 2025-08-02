"""
New modular Flask application entry point
"""
import os
import threading
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from apscheduler.schedulers.background import BackgroundScheduler

# Import our modular components
from src.config.database import init_db
from src.config.scheduler import init_scheduler
from src.routes.scan_routes import create_scan_blueprint
from src.routes.settings_routes import create_settings_blueprint
from src.routes.schedule_routes import create_schedule_blueprint
from src.routes.api_routes import create_api_blueprint
from src.services.whats_up import whats_up_monitor

# Global instances
db = None
socketio = None
scheduler = None

def create_app():
    """Application factory pattern"""
    global db, socketio, scheduler
    
    # Create Flask app
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = 'sentinelzero-dev-key-change-in-production'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/sentinelzero.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db = init_db(app)
    socketio = SocketIO(app, cors_allowed_origins="*")
    scheduler = init_scheduler()
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Register blueprints
    app.register_blueprint(create_scan_blueprint(db, socketio), url_prefix='/api')
    app.register_blueprint(create_settings_blueprint(db), url_prefix='/api')
    app.register_blueprint(create_schedule_blueprint(db, socketio, scheduler), url_prefix='/api')
    app.register_blueprint(create_api_blueprint(db), url_prefix='/api')
    
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
        print('📡 Backend Server: http://localhost:5000')
        print('🌐 Frontend (dev): http://localhost:3174') 
        print('📊 Dashboard: http://localhost:3174/dashboard')
        print('⚙️  Settings: http://localhost:3174/settings')
        print('='*60)
        print('🔍 Starting scan engine...')
        print('📡 Initializing network monitoring...')
        print('🚀 Server ready!')
        print('='*60)
        
        # Run with SocketIO
        socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    main()
