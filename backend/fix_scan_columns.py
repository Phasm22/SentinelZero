from app import app, db
from sqlalchemy import text

with app.app_context():
    with db.engine.connect() as conn:
        try:
            conn.execute(text('ALTER TABLE scan ADD COLUMN status VARCHAR(32) DEFAULT "pending"'))
            print('Added status column')
        except Exception as e:
            print('status column:', e)
        try:
            conn.execute(text('ALTER TABLE scan ADD COLUMN percent FLOAT DEFAULT 0.0'))
            print('Added percent column')
        except Exception as e:
            print('percent column:', e) 