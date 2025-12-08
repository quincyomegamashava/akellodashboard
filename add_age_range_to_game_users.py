"""
Migration script to add age_range column to game_users table
Run this script to add the age_range column and populate it for existing users.
"""

from app import app, db
from app.models import GameUser

def add_age_range_column():
    """Add age_range column to game_users table and populate it for existing users"""
    with app.app_context():
        try:
            # Add the column using raw SQL (SQLAlchemy doesn't support adding columns directly in migrations)
            # First, check if column already exists
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('game_users')]
            
            if 'age_range' not in columns:
                print("Adding age_range column to game_users table...")
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE game_users ADD COLUMN age_range VARCHAR(50)"))
                    conn.commit()
                print("✓ Column added successfully")
            else:
                print("✓ age_range column already exists")
            
            # Populate age_range for existing users
            print("\nUpdating age_range for existing users...")
            users = GameUser.query.all()
            updated_count = 0
            
            for user in users:
                if not user.age_range:  # Only update if age_range is None
                    user.age_range = user.determine_age_range()
                    updated_count += 1
            
            if updated_count > 0:
                db.session.commit()
                print(f"✓ Updated age_range for {updated_count} existing user(s)")
            else:
                print("✓ All users already have age_range set")
            
            print("\nMigration completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error during migration: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == '__main__':
    add_age_range_column()

