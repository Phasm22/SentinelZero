"""
API routes initialization
"""
from flask import Blueprint

def init_routes(app, db, socketio, scheduler):
    """Initialize all route blueprints"""
    
    # Import route modules
    from .scan_routes import create_scan_blueprint
    from .settings_routes import create_settings_blueprint
    from .schedule_routes import create_schedule_blueprint
    from .api_routes import create_api_blueprint
    from .whatsup_routes import bp as whatsup_bp
    
    # Register blueprints
    app.register_blueprint(create_scan_blueprint(db, socketio))
    app.register_blueprint(create_settings_blueprint(db))
    app.register_blueprint(create_schedule_blueprint(db, socketio, scheduler))
    app.register_blueprint(create_api_blueprint(db))
    app.register_blueprint(whatsup_bp)
    
    return app
