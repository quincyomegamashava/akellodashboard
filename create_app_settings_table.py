"""
Database migration script to create app_settings table and initialize ASL MTD filter settings.

Run this script to set up the admin controls feature:
    python create_app_settings_table.py
"""

from app import app, db
from app.models import AppSetting
from sqlalchemy import text

def create_app_settings_table():
    """Create the app_settings table if it doesn't exist"""
    with app.app_context():
        try:
            # Create table using raw SQL to ensure compatibility
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS app_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key VARCHAR(100) UNIQUE NOT NULL,
                setting_value VARCHAR(500) NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER,
                FOREIGN KEY (updated_by) REFERENCES user(id)
            );
            """
            
            db.session.execute(text(create_table_sql))
            db.session.commit()
            print("✓ app_settings table created successfully")
            
            # Initialize default settings
            initialize_default_settings()
            
        except Exception as e:
            print(f"✗ Error creating table: {e}")
            db.session.rollback()

def initialize_default_settings():
    """Initialize default ASL MTD filter settings"""
    try:
        # Check if settings already exist
        existing_12_months = AppSetting.query.filter_by(setting_key='asl_mtd_exclude_12_months').first()
        existing_1_year = AppSetting.query.filter_by(setting_key='asl_mtd_exclude_1_year_awarded').first()
        
        if not existing_12_months:
            setting_12_months = AppSetting(
                setting_key='asl_mtd_exclude_12_months',
                setting_value='true',
                description='Exclude schools with 12+ months scholarship duration from ASL MTD'
            )
            db.session.add(setting_12_months)
            print("✓ Initialized 'asl_mtd_exclude_12_months' setting to 'true'")
        else:
            print("  'asl_mtd_exclude_12_months' setting already exists")
        
        if not existing_1_year:
            setting_1_year = AppSetting(
                setting_key='asl_mtd_exclude_1_year_awarded',
                setting_value='true',
                description='Exclude schools where first scholarship awarded >1 year ago from ASL MTD'
            )
            db.session.add(setting_1_year)
            print("✓ Initialized 'asl_mtd_exclude_1_year_awarded' setting to 'true'")
        else:
            print("  'asl_mtd_exclude_1_year_awarded' setting already exists")
        
        db.session.commit()
        print("\n✓ Default settings initialized successfully")
        
    except Exception as e:
        print(f"✗ Error initializing settings: {e}")
        db.session.rollback()

if __name__ == '__main__':
    print("Creating app_settings table and initializing default settings...\n")
    create_app_settings_table()
    print("\nDone!")
