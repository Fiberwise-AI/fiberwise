"""
CLI command to create seed users for FiberWise.

DEFAULT CREDENTIALS:
===================
Username: admin
Email: admin@fiberwise.local  
Password: fiber2025!
Role: Admin

These are the default development credentials. Change them in production!
"""

import asyncio
import click
import uuid
import getpass
import socket
from typing import Optional

@click.command()
@click.option('--username', default='admin', help='Username for the new user (default: admin)')
@click.option('--email', default='admin@fiberwise.local', help='Email for the new user (default: admin@fiberwise.local)')
@click.option('--display-name', help='Display name for the user (default: Auto-generated)')
@click.option('--admin', is_flag=True, default=True, help='Make the user an admin (default: True)')
@click.option('--password', default='fiber2025!', help='Password for the user (default: fiber2025!)')
@click.option('--force', is_flag=True, help='Overwrite existing user if it exists')
def seed_user(username: str, email: str, display_name: Optional[str], admin: bool, password: Optional[str], force: bool):
    """
    Create a seed user for FiberWise.
    
    DEFAULT CREDENTIALS (Development):
    - Username: admin
    - Email: admin@fiberwise.local
    - Password: fiber2025!
    - Role: Admin
    
    This command creates a new user in the FiberWise database with default FiberWise credentials.
    The default password is 'fiber2025!' - remember to change this in production!
    
    Examples:
        fiber seed-user                                           # Create default admin user
        fiber seed-user --username john --email john@company.com # Create custom user
        fiber seed-user --force                                   # Overwrite existing admin user
    """
    
    # Use default display name if not provided
    if not display_name:
        if username == 'admin':
            display_name = 'FiberWise Administrator'
        else:
            display_name = username.title()
    
    # Show the credentials being used
    click.echo("=" * 50)
    click.echo("CREATING FIBERWISE USER")
    click.echo("=" * 50)
    click.echo(f"Username: {username}")
    click.echo(f"Email: {email}")
    click.echo(f"Display Name: {display_name}")
    click.echo(f"Password: {'*' * len(password) if password else 'Will prompt'}")
    click.echo(f"Admin: {'Yes' if admin else 'No'}")
    click.echo("=" * 50)
    
    asyncio.run(create_seed_user(username, email, display_name, admin, password, force))

async def create_seed_user(username: str, email: str, display_name: Optional[str], admin: bool, password: Optional[str], force: bool):
    """Create a seed user asynchronously."""
    
    # Import here to avoid circular dependencies
    import sys
    import os
    from pathlib import Path
    

    
    from fiberwise_common.database.factory import get_database_provider
    from fiberwise_common.database.sqlite import SQLiteProvider
    
    # Set up database connection using the same config as the web app
    db_path = Path.home() / ".fiberwise" / "fiberwise.db"
    database_url = f"sqlite:///{db_path}"
    
    click.echo(f"[SEED] Connecting to database: {database_url}")
    
    # Create a simple settings-like object for the database factory
    class Settings:
        DB_PROVIDER = "sqlite"
        DATABASE_URL = database_url
        ENVIRONMENT = "development"
        DEBUG = True
    
    settings = Settings()
    
    try:
        db_provider = get_database_provider(settings)
        await db_provider.connect()
        click.echo("[SEED] Database connection successful")
        
        # Check if user already exists
        existing_user = await db_provider.fetchrow(
            "SELECT id, username, email FROM users WHERE username = ? OR email = ?",
            username, email
        )
        
        if existing_user and not force:
            click.echo(f"[ERROR] User already exists: {existing_user['username']} ({existing_user['email']})")
            click.echo("Use --force flag to overwrite existing user")
            return
        
        if existing_user and force:
            click.echo(f"[SEED] Overwriting existing user: {existing_user['username']}")
            await db_provider.execute(
                "DELETE FROM users WHERE id = ?",
                existing_user['id']
            )
        
        # Get password if not provided
        if not password:
            password = getpass.getpass("Enter password: ")
            confirm_password = getpass.getpass("Confirm password: ")
            
            if password != confirm_password:
                click.echo("[ERROR] Passwords do not match")
                return
        
        # Hash password using the same method as the user service
        from fiberwise_common.services.user_service import get_password_hash
        hashed_password = get_password_hash(password)
        
        # Generate UUID and set defaults
        user_uuid = str(uuid.uuid4())
        if not display_name:
            display_name = username.title()
        
        # Create full name from display name
        full_name = display_name
        
        # Create the user
        click.echo(f"[SEED] Creating user: {username} ({email})")
        
        await db_provider.execute(
            """INSERT INTO users (
                uuid, username, email, display_name, hashed_password,
                is_active, is_admin, is_superuser, is_verified,
                full_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            user_uuid, username, email, display_name, hashed_password,
            1, 1 if admin else 0, 1 if admin else 0, 1,
            full_name
        )
        
        # Verify user was created
        created_user = await db_provider.fetchrow(
            "SELECT id, username, email, is_admin FROM users WHERE username = ?",
            username
        )
        
        if created_user:
            admin_status = "admin" if created_user['is_admin'] else "regular user"
            click.echo(f"[SUCCESS] User created successfully!")
            click.echo(f"  ID: {created_user['id']}")
            click.echo(f"  Username: {created_user['username']}")
            click.echo(f"  Email: {created_user['email']}")
            click.echo(f"  Role: {admin_status}")
        else:
            click.echo("[ERROR] Failed to create user")
        
    except Exception as e:
        click.echo(f"[ERROR] Failed to create user: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            await db_provider.disconnect()
        except:
            pass

def get_system_user():
    """Get the current system user info."""
    try:
        username = getpass.getuser()
        hostname = socket.gethostname()
        email = f"{username}@{hostname}.local"
        return username, email
    except:
        return "admin", "admin@localhost.local"

@click.command()
@click.option('--force', is_flag=True, help='Overwrite existing system user if it exists')
def seed_system_user(force: bool):
    """
    Create a seed system user based on the current system user.
    
    This command creates an admin user based on the current system username and hostname.
    This is useful for development and initial setup.
    
    Examples:
        fiber seed-system-user
        fiber seed-system-user --force
    """
    username, email = get_system_user()
    click.echo(f"[SEED] Creating system user: {username} ({email})")
    
    # Use a default FiberWise password for system user
    password = "fiber2025!"
    display_name = f"{username.title()} (System)"
    
    asyncio.run(create_seed_user(username, email, display_name, admin=True, password=password, force=force))

if __name__ == "__main__":
    seed_user()
