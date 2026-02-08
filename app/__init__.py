from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
import atexit

db = SQLAlchemy()

# Global scheduler instance
scheduler = None

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-please-change-in-production')
    
    # Handle Render PostgreSQL URI (which starts with postgres:// but SQLAlchemy needs postgresql://)
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///app.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions
    db.init_app(app)

    with app.app_context():
        # Import parts of our application
        from . import routes, models
        from .routes import main_bp
        app.register_blueprint(main_bp)

        # Create database tables
        db.create_all()

        # Database migration logic
        # We wrap this in a check to ensure we only run it when needed
        try:
            # Check if we are using SQLite or PostgreSQL
            engine_name = db.engine.name
            
            if engine_name == 'sqlite':
                # SQLite PRAGMA check
                with db.engine.begin() as conn:
                    result = conn.execute(db.text("PRAGMA table_info(campaign)"))
                    cols = [row[1] for row in result.fetchall()]
                    
                    if 'scheduled_at' not in cols:
                        conn.execute(db.text("ALTER TABLE campaign ADD COLUMN scheduled_at DATETIME"))
                    if 'sender_email' not in cols:
                        conn.execute(db.text("ALTER TABLE campaign ADD COLUMN sender_email VARCHAR(120)"))
                    if 'sender_password' not in cols:
                        conn.execute(db.text("ALTER TABLE campaign ADD COLUMN sender_password VARCHAR(255)"))
                    if 'batch_size' not in cols:
                        conn.execute(db.text("ALTER TABLE campaign ADD COLUMN batch_size INTEGER DEFAULT 50"))
                    if 'batch_delay' not in cols:
                        conn.execute(db.text("ALTER TABLE campaign ADD COLUMN batch_delay INTEGER DEFAULT 5"))
                    
                    result = conn.execute(db.text("PRAGMA table_info(recipient)"))
                    recipient_cols = [row[1] for row in result.fetchall()]
                    if 'name' not in recipient_cols:
                        conn.execute(db.text("ALTER TABLE recipient ADD COLUMN name VARCHAR(100)"))
                    if 'dob' not in recipient_cols:
                        conn.execute(db.text("ALTER TABLE recipient ADD COLUMN dob DATE"))
            else:
                # Basic PostgreSQL column check (generic SQL)
                # Note: For production, using Flask-Migrate is better, but this handles simple additions
                with db.engine.begin() as conn:
                    # Check for Campaign columns
                    for col_name, col_type in [
                        ('scheduled_at', 'TIMESTAMP'),
                        ('sender_email', 'VARCHAR(120)'),
                        ('sender_password', 'VARCHAR(255)'),
                        ('batch_size', 'INTEGER DEFAULT 50'),
                        ('batch_delay', 'INTEGER DEFAULT 5')
                    ]:
                        try:
                            conn.execute(db.text(f"ALTER TABLE campaign ADD COLUMN {col_name} {col_type}"))
                        except Exception:
                            pass # Column likely exists
                            
                    # Check for Recipient columns
                    for col_name, col_type in [
                        ('name', 'VARCHAR(100)'),
                        ('dob', 'DATE')
                    ]:
                        try:
                            conn.execute(db.text(f"ALTER TABLE recipient ADD COLUMN {col_name} {col_type}"))
                        except Exception:
                            pass
        except Exception as e:
            print(f"⚠️  Database migration skipped: {e}")
    
    # Setup APScheduler for automatic birthday wishes
    setup_scheduler(app)

    return app

def setup_scheduler(app):
    """
    Set up APScheduler to run daily birthday checks.
    """
    global scheduler
    
    if scheduler is not None:
        return
    
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        
        # PREVENT DOUBLE RUN:
        # 1. In development (Flask reloader), only start in the reloader process.
        # 2. In production (Gunicorn), we start it. Note: If using multiple workers, 
        #    you'd usually use a separate process for the scheduler.
        
        is_dev = os.environ.get('FLASK_ENV') != 'production'
        is_reloader = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        
        if is_dev and not is_reloader:
            return

        scheduler = BackgroundScheduler(daemon=True)
        
        # Schedule daily birthday check
        scheduler.add_job(
            func=lambda: check_and_send_birthday_emails_wrapper(app),
            trigger='cron',
            hour=9,   # Run at 9:00 AM
            minute=0,
            id='birthday_check',
            name='Daily Birthday Check',
            replace_existing=True
        )
        
        scheduler.start()
        print(f"✅ Birthday scheduler started - daily checks at 09:00 AM")
        
        atexit.register(lambda: scheduler.shutdown() if scheduler else None)
        
    except Exception as e:
        print(f"⚠️  Failed to start birthday scheduler: {e}")

def check_and_send_birthday_emails_wrapper(app):
    """
    Wrapper function to ensure Flask app context is available.
    """
    with app.app_context():
        from .birthday_scheduler import check_and_send_birthday_emails
        check_and_send_birthday_emails()


