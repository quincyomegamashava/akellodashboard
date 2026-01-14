"""
Script to create an Admin user manually
Run this script to create an admin user with the specified credentials.
"""

from app import app, db
from app.models import User
import sqlalchemy as sa

def create_admin_user():
    """Create an admin user with the specified credentials"""
    with app.app_context():
        try:
            # User details
            username = "QuincyOMashava"
            email = "quincyomashava@akello.local"
            firstname = "Quincy"
            lastname = "Mashava"
            userRole = "Admin"
            password = "def4ult123"
            
            # Check if user with this username already exists
            existing_user = db.session.scalar(sa.select(User).where(User.username == username))
            if existing_user:
                print(f"❌ User with username '{username}' already exists!")
                print(f"   User ID: {existing_user.id}")
                print(f"   Email: {existing_user.email}")
                return False
            
            # Check if user with this email already exists
            existing_email = db.session.scalar(sa.select(User).where(User.email == email))
            if existing_email:
                print(f"❌ User with email '{email}' already exists!")
                print(f"   Username: {existing_email.username}")
                print(f"   User ID: {existing_email.id}")
                return False
            
            # Create new user
            print(f"Creating admin user '{username}'...")
            user = User(
                username=username,
                email=email,
                firstname=firstname,
                lastname=lastname,
                userRole=userRole
            )
            
            # Set password (this will hash it automatically)
            user.set_password(password)
            
            # Add user to database
            db.session.add(user)
            db.session.commit()
            
            print(f"✓ Admin user created successfully!")
            print(f"   Username: {username}")
            print(f"   Email: {email}")
            print(f"   Name: {firstname} {lastname}")
            print(f"   Role: {userRole}")
            print(f"   User ID: {user.id}")
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating admin user: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    create_admin_user()
