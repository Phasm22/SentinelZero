"""
Database configuration and initialization
"""
from flask_sqlalchemy import SQLAlchemy

# Global database instance
db = SQLAlchemy()

def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)
    return db
