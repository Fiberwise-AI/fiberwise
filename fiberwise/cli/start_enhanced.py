import click
import uvicorn
import webbrowser
import sys
import asyncio
import time
import threading
import socket
import os
import uuid
import getpass
import subprocess
import tempfile
from pathlib import Path
from fiberwise_common.entities.config import Config
from fiberwise_common.constants import (
    CLI_APP_UUID, 
    CLI_APP_SLUG,
    get_cli_app_name, 
    get_cli_app_description,
    get_cli_user_email,
    CLI_APP_VERSION
)

# Import for password hashing fallback
try:
    from passlib.context import CryptContext
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:
    _pwd_context = None

# Global variables to track worker process
_worker_process = None

def start_background_worker(verbose: bool = False) -> bool:
    """Start the background worker process using fiberwise-common worker system"""
    global _worker_process
    
    try:
        # Create a Python script that runs the new common worker system
        worker_script_content = '''
import asyncio
import sys
import logging
from pathlib import Path


async def main():
    try:
        from fiberwise_common.worker import get_worker_provider, WorkerConfig, WorkerType
        from fiberwise_common.database import DatabaseManager
        from fiberwise.web.api.core.config import CoreWebSettings
        
        # Initialize database using web settings
        settings = CoreWebSettings()
        db_manager = DatabaseManager.create_from_settings(settings)
        await db_manager.initialize()
        db_provider = db_manager.get_provider()
        
        print(f"[OK] Worker connected to {settings.database_provider} database")
        print(f"[DB] Database: {settings.effective_database_url}")
        
        # Create worker configuration
        from fiberwise_common.worker.base import WorkerConfig, WorkerType
        config = WorkerConfig(
            worker_type=WorkerType.LOCAL,
            poll_interval=5,
            max_concurrent_jobs=2
        )
        
        # Create the worker using the factory
        from fiberwise_common.worker.factory import WorkerFactory
        worker = WorkerFactory.create_worker(config, db_provider)
        
        print("[WORKER] Starting fiberwise-common worker system...")
        print(f"[WORKER] Type: {config.worker_type.value}")
        print(f"[WORKER] Polling interval: {config.poll_interval}s")
        print(f"[WORKER] Max concurrent jobs: {config.max_concurrent_jobs}")
        print("[WORKER] Press Ctrl+C to stop")
        print("=" * 50)
        
        await worker.start()
        
    except KeyboardInterrupt:
        print("\\n[STOP] Worker stopped by user")
    except Exception as e:
        print(f"[ERROR] Worker error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'worker' in locals():
            await worker.stop()
        if 'db_manager' in locals():
            await db_manager.shutdown()
            print("[DB] Database connection closed")

if __name__ == "__main__":
    asyncio.run(main())
'''
        
        # Write the worker script to a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(worker_script_content)
            temp_worker_script = f.name
        
        worker_cmd = [sys.executable, temp_worker_script]
        
        if verbose:
            click.echo(f"   🔧 Starting fiberwise-common worker system")
            click.echo(f"   📁 Using provider pattern with local database worker")
        
        # Start worker process
        _worker_process = subprocess.Popen(
            worker_cmd,
            stdout=None,  # Let worker output show in terminal
            stderr=None,  # Let worker errors show in terminal
            text=True
        )
        
        if verbose:
            click.echo("   ✅ Common worker system started")
        
        return True
        
    except Exception as e:
        if verbose:
            click.echo(f"   ❌ Failed to start common worker: {e}")
        return False

def stop_background_worker(verbose: bool = False):
    """Stop the background worker process"""
    global _worker_process
    
    if _worker_process:
        try:
            _worker_process.terminate()
            _worker_process.wait(timeout=5)
            if verbose:
                click.echo("   ✅ Background worker stopped")
        except subprocess.TimeoutExpired:
            _worker_process.kill()
            if verbose:
                click.echo("   ⚠️ Background worker force-killed")
        except Exception as e:
            if verbose:
                click.echo(f"   ❌ Error stopping worker: {e}")
        finally:
            _worker_process = None

def check_port_available(host: str, port: int) -> bool:
    """Check if a port is available for binding"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False

def open_browser_delayed(host: str, port: int, delay: float = 1.5):
    """Open browser to the web server URL after a delay"""
    def _open():
        time.sleep(delay)
        url = f"http://{host}:{port}"
        try:
            webbrowser.open(url)
            click.echo(f"Browser opened to {url}")
        except Exception as e:
            click.echo(f"Warning: Could not open browser: {e}")
    
    thread = threading.Thread(target=_open, daemon=True)
    thread.start()

def find_core_web_path():
    """Find the fiberwise-core-web directory using pip package location (supports editable installs)"""
    try:
        import importlib.util
        
        # Use the modern importlib approach to find package path (same as initialize.py)
        spec = importlib.util.find_spec('fiberwise')
        
        if spec and spec.origin:
            # For regular packages, origin points to __init__.py - we want the parent directory
            package_dir = Path(spec.origin).parent
        elif spec and spec.submodule_search_locations:
            # For namespace packages (like editable installs), use the first search location
            search_locations = list(spec.submodule_search_locations)
            if search_locations:
                package_dir = Path(search_locations[0])
            else:
                return None
        else:
            # Fallback: try importing and using __file__ if available
            try:
                import fiberwise
                if hasattr(fiberwise, '__file__') and fiberwise.__file__:
                    package_dir = Path(fiberwise.__file__).parent
                else:
                    return None
            except:
                return None
        
        # Check for the web directory (created by fiber initialize)
        web_dir = package_dir / "web"
        if web_dir.exists() and (web_dir / "main.py").exists():
            return web_dir
        
        return None
        
    except Exception:
        return None

def check_fiberwise_initialized():
    """Check if fiberwise has been initialized properly"""
    try:
        import importlib.util
        
        # Check if fiberwise package can be found
        spec = importlib.util.find_spec('fiberwise')
        if not spec:
            return False, "Fiberwise package not found"
        
        # Get package directory
        if spec.origin:
            package_dir = Path(spec.origin).parent
        elif spec.submodule_search_locations:
            search_locations = list(spec.submodule_search_locations)
            if search_locations:
                package_dir = Path(search_locations[0])
            else:
                return False, "Cannot determine package location"
        else:
            return False, "Cannot determine package location"
        
        # Check if web directory exists (created by fiber initialize)
        web_dir = package_dir / "web"
        if not web_dir.exists():
            return False, "Web directory not found. Run 'fiber initialize' first."
        
        # Check if main.py exists in web directory
        main_py = web_dir / "main.py"
        if not main_py.exists():
            return False, "Web main.py not found. Run 'fiber initialize' first."
        
        return True, "Fiberwise is properly initialized"
        
    except Exception as e:
        return False, f"Error checking initialization: {e}"


def _setup_development_mode(verbose: bool, port: int, vite_port: int) -> bool:
    """Set up development mode with Vite integration."""
    try:
        if verbose:
            click.echo("🔧 Setting up development mode...")
        
        # Find fiberwise-core-web directory (now returns web directory directly)
        core_web_path = find_core_web_path()
        
        if not core_web_path:
            if verbose:
                click.echo("   ⚠️  fiberwise web directory not found, skipping Vite setup")
                click.echo("   💡  Run 'fiber initialize' to set up web components")
            return True
        
        if verbose:
            click.echo(f"   Found fiberwise web directory at: {core_web_path}")
        
        # Check if Vite is available and configured (in fiberwise_core subdirectory)
        fiberwise_core_path = core_web_path / "fiberwise_core"
        vite_config = fiberwise_core_path / "vite.config.js"
        package_json = fiberwise_core_path / "package.json"
        
        if not vite_config.exists() or not package_json.exists():
            if verbose:
                click.echo("   ⚠️  Vite configuration not found, skipping Vite integration")
                click.echo("   💡  Run 'fiber initialize' to set up web components properly")
            return True
        
        # Check if node_modules exists in the fiberwise_core directory
        node_modules = fiberwise_core_path / "node_modules"
        if not node_modules.exists():
            if verbose:
                click.echo("   📦 Installing dependencies for development mode...")
            
            try:
                import subprocess
                result = subprocess.run(
                    ["npm", "install"],
                    cwd=fiberwise_core_path,  # Run npm install in fiberwise_core directory
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minutes timeout
                )
                
                if result.returncode == 0:
                    if verbose:
                        click.echo("   ✅ Dependencies installed")
                else:
                    if verbose:
                        click.echo("   ⚠️  Dependency installation failed, continuing anyway")
                    
            except Exception as e:
                if verbose:
                    click.echo(f"   ⚠️  Error installing dependencies: {e}")
        
        # Start Vite dev server in the background
        if verbose:
            click.echo("   🚀 Starting Vite development server...")
        
        success = _start_vite_dev_server(fiberwise_core_path, verbose, port, vite_port)
        if success:
            if verbose:
                click.echo("   ✅ Development mode setup completed")
        else:
            if verbose:
                click.echo("   ⚠️  Vite dev server setup failed, continuing without it")
        
        return True
        
    except Exception as e:
        if verbose:
            click.echo(f"   ❌ Error setting up development mode: {e}")
        return False


def _start_vite_dev_server(fiberwise_core_path: Path, verbose: bool, port: int, vite_port: int) -> bool:
    """Start Vite development server in the background."""
    try:
        import subprocess
        import threading
        import time
        
        # Vite config is in the fiberwise_core directory
        web_dir = fiberwise_core_path
        
        def run_vite():
            try:
                # Try different approaches to start Vite dev server
                commands = [
                    ["npm", "run", "dev"],
                    ["npx", "vite", "dev", "--port", str(vite_port)],
                    # Try using node_modules binary directly (Windows)
                    [os.path.join(web_dir, "node_modules", ".bin", "vite.cmd"), "dev", "--port", str(vite_port)],
                    # Try using node to run vite directly
                    ["node", os.path.join(web_dir, "node_modules", "vite", "bin", "vite.js"), "dev", "--port", str(vite_port)]
                ]
                
                for cmd in commands:
                    try:
                        if verbose:
                            click.echo(f"   🔧 Running: {' '.join(cmd)} in {web_dir}")
                        
                        # Create a copy of the current environment and add Vite-specific variables
                        env = os.environ.copy()
                        env['VITE_DEV_PORT'] = str(vite_port)
                        env['VITE_API_TARGET'] = f'http://localhost:{port}'
                        
                        process = subprocess.Popen(
                            cmd,
                            cwd=web_dir,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,  # Combine stderr with stdout
                            text=True,
                            env=env,  # Pass environment variables
                            bufsize=1,  # Line buffered
                            universal_newlines=True
                        )
                        
                        # Store process reference for cleanup
                        if not hasattr(_start_vite_dev_server, '_vite_process'):
                            _start_vite_dev_server._vite_process = []
                        _start_vite_dev_server._vite_process.append(process)
                        
                        # Read output to check if server started successfully
                        startup_timeout = 10  # Wait up to 10 seconds for startup
                        start_time = time.time()
                        server_started = False
                        
                        while time.time() - start_time < startup_timeout:
                            if process.poll() is not None:
                                # Process ended, read any remaining output
                                output = process.stdout.read()
                                if verbose and output:
                                    click.echo(f"   📋 Vite output: {output.strip()}")
                                break
                                
                            # Try to read a line with timeout
                            try:
                                line = process.stdout.readline()
                                if line:
                                    if verbose:
                                        click.echo(f"   📋 Vite: {line.strip()}")
                                    
                                    # Check for successful startup messages
                                    if ("ready in" in line.lower() or 
                                        "local:" in line.lower() or 
                                        "vite v" in line.lower() or
                                        f":{vite_port}" in line):
                                        server_started = True
                                        if verbose:
                                            click.echo(f"   ✅ Vite dev server started on port {vite_port}")
                                            click.echo(f"   📁 Frontend available at: http://localhost:{vite_port}")
                                        break
                            except:
                                pass
                            
                            time.sleep(0.1)
                        
                        if server_started:
                            return True
                        elif process.poll() is None:
                            # Still running but no startup confirmation
                            if verbose:
                                click.echo(f"   ⚠️  Vite server may be starting, check http://localhost:{vite_port}")
                            return True
                        else:
                            # Process ended
                            if verbose:
                                click.echo(f"   ❌ Vite process ended with code {process.returncode}")
                            continue
                        
                    except FileNotFoundError:
                        if verbose:
                            click.echo(f"   ⚠️  Command not found: {cmd[0]}")
                        continue
                    except Exception as e:
                        if verbose:
                            click.echo(f"   ❌ Error running {cmd[0]}: {e}")
                        continue
                        
                if verbose:
                    click.echo("   ❌ All Vite startup commands failed")
                return False
                        
            except Exception as e:
                if verbose:
                    click.echo(f"   ❌ Failed to start Vite: {e}")
                return False
        
        # Start Vite in a background thread
        if verbose:
            click.echo("   🚀 Starting Vite development server...")
            
        vite_thread = threading.Thread(target=run_vite, daemon=True)
        vite_thread.start()
        
        # Give it a moment to start
        time.sleep(2)
        
        return True
        
    except Exception as e:
        if verbose:
            click.echo(f"   ❌ Error starting Vite dev server: {e}")
        return False

async def _run_common_migrations_and_setup(config: Config, verbose: bool = False) -> bool:
    """Use the DatabaseManager system like web application."""
    try:
        if verbose:
            click.echo("Initializing database...")
        
        # Initialize database connection using DatabaseManager (same as web)
        success = await config.db_manager.initialize()
        if not success:
            click.echo("[ERROR] Database initialization failed", err=True)
            return False
        
        if verbose:
            click.echo("Applying database migrations...")
        
        # Apply migrations using DatabaseManager (same as web)
        migration_success = await config.db_manager.apply_migrations()
        if migration_success:
            if verbose:
                click.echo("[OK] Database migrations applied successfully")
        else:
            if verbose:
                click.echo("[WARNING] Some migrations may have failed")
        
        # Ensure user and app exist using provider directly - force API key creation during init
        user_ok, app_ok = await _ensure_default_user_and_app(config.db_provider, verbose, force_api_key=True)
        if not (user_ok and app_ok):
            click.echo("[ERROR] Failed to ensure default user and app exist", err=True)
            return False
        
        if verbose:
            click.echo("[OK] Database initialization completed")
        
        return True
        
    except Exception as e:
        click.echo(f"[ERROR] Database initialization failed: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        return False

async def _create_default_api_key(db_provider, user_id: int, organization_id: int, verbose: bool = False) -> str:
    """
    Create a default API key for CLI usage.
    
    Args:
        db_provider: Database provider instance
        user_id: User ID to associate with the API key
        organization_id: Organization ID to associate with the API key
        verbose: Whether to show verbose output
    
    Returns:
        str: The raw API key string for immediate use
    """
    try:
        import uuid
        import hashlib
        import json
        
        # Check if user already has API keys
        existing_keys = await db_provider.fetch_all(
            "SELECT id FROM api_keys WHERE user_id = ? LIMIT 1", user_id
        )
        
        if existing_keys:
            if verbose:
                click.echo("[OK] API key already exists for user")
            return None
        
        # Generate API key
        raw_key = str(uuid.uuid4())
        key_prefix = raw_key[:8]
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Default scopes for CLI usage
        scopes = ["read:all", "write:all", "app:access"]
        scopes_json = json.dumps(scopes)
        
        # Insert API key
        await db_provider.execute(
            """INSERT INTO api_keys (user_id, organization_id, key_prefix, key_hash, name, scopes, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            user_id, organization_id, key_prefix, hashed_key, "Default CLI Key", scopes_json
        )
        
        if verbose:
            click.echo(f"[OK] Created default API key: {key_prefix}...")
            click.echo(f"[INFO] API key: {raw_key}")
            click.echo(f"[INFO] Set environment variable: export FIBERWISE_API_KEY={raw_key}")
        
        # Save API key to config file for easy access
        await _save_api_key_to_config(raw_key, verbose)
        
        return raw_key
        
    except Exception as e:
        if verbose:
            click.echo(f"[WARNING] Failed to create default API key: {e}")
        return None

async def _save_api_key_to_config(api_key: str, verbose: bool = False):
    """Save API key to ~/.fiberwise/configs/default.json for CLI access."""
    try:
        import json
        from pathlib import Path
        from datetime import datetime
        
        # Create configs directory (new config system)
        config_dir = Path.home() / ".fiberwise"
        configs_dir = config_dir / "configs"
        configs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create default configuration
        config_data = {
            "name": "local",
            "api_key": api_key,
            "base_url": "http://127.0.0.1:8000",  # Default server port
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Save to new config system
        config_file = configs_dir / "local.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        # Set as default configuration
        default_file = config_dir / "default_config.txt"
        with open(default_file, 'w') as f:
            f.write("local")
        
        if verbose:
            click.echo(f"[OK] Created local configuration: {config_file}")
            click.echo(f"[OK] Set as default config for CLI commands")
        
            
    except Exception as e:
        if verbose:
            click.echo(f"[WARNING] Failed to save API key config: {e}")

async def _ensure_default_user_and_app(db_provider, verbose: bool = False, force_api_key: bool = False) -> tuple[bool, bool]:
    """
    Simple CLI check to ensure at least 1 user and 1 app exist.
    Creates them if missing using the CLI constants.
    
    Args:
        db_provider: Database provider instance
        verbose: Enable verbose output
        force_api_key: Force creation of API key even if user already exists
    
    Returns:
        tuple[bool, bool]: (user_exists_or_created, app_exists_or_created)
    """
    
    try:
        # Check for users
        users = await db_provider.fetch_all("SELECT id, username FROM users LIMIT 1")
        user_created = False
        user_id = None
        
        if not users:
            # Create default CLI user
            system_username = getpass.getuser()
            user_email = get_cli_user_email()
            user_uuid = str(uuid.uuid4())
            
            # Hash the default password
            try:
                from fiberwise.web.api.core.security import get_password_hash
                default_password = "fiber2025!"
                hashed_password = get_password_hash(default_password)
            except ImportError:
                # Fallback to bcrypt directly if web module not available
                if _pwd_context:
                    default_password = "fiber2025!"
                    hashed_password = _pwd_context.hash(default_password)
                else:
                    # Final fallback - create user without password (will need to use seed-user command)
                    click.echo("[WARNING] Password hashing not available. User created without password.", err=True)
                    click.echo("[WARNING] Use 'fiber seed-user' command to set password.", err=True)
                    default_password = None
                    hashed_password = None
            
            if verbose:
                click.echo(f"Creating default user: {system_username}")
                if default_password:
                    click.echo(f"Default password: {default_password}")
            
            if hashed_password:
                await db_provider.execute(
                    """INSERT INTO users (uuid, username, email, display_name, hashed_password, is_active, is_admin) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    user_uuid, system_username, user_email, system_username.title(), hashed_password, 1, 1
                )
            else:
                # Create user without password if hashing failed
                await db_provider.execute(
                    """INSERT INTO users (uuid, username, email, display_name, is_active, is_admin) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    user_uuid, system_username, user_email, system_username.title(), 1, 1
                )
            
            # Get the created user
            created_user = await db_provider.fetch_one("SELECT id FROM users WHERE username = ?", system_username)
            if created_user:
                user_id = created_user['id']
                user_created = True
                if verbose:
                    click.echo(f"[OK] Created user: {system_username} (ID: {user_id})")
        else:
            user_id = users[0]['id']
            if verbose:
                click.echo(f"[OK] User exists: {users[0]['username']} (ID: {user_id})")
        
        if not user_id:
            click.echo("[ERROR] Failed to create or find user", err=True)
            return False, False
        
        # Check for organizations
        organizations = await db_provider.fetch_all("SELECT id, name FROM organizations LIMIT 1")
        org_id = None
        
        if not organizations:
            # Create default organization
            import uuid as uuid_module
            org_uuid = str(uuid_module.uuid4())
            org_name = "Default Organization"
            org_slug = "default"
            
            if verbose:
                click.echo(f"Creating default organization: {org_name}")
            
            await db_provider.execute(
                """INSERT INTO organizations (uuid, name, display_name, slug, created_by) 
                   VALUES (?, ?, ?, ?, ?)""",
                org_uuid, org_name, org_name, org_slug, user_id
            )
            
            # Get the created organization
            created_org = await db_provider.fetch_one("SELECT id FROM organizations WHERE slug = ?", org_slug)
            if created_org:
                org_id = created_org['id']
                if verbose:
                    click.echo(f"[OK] Created organization: {org_name} (ID: {org_id})")
        else:
            org_id = organizations[0]['id']
            if verbose:
                click.echo(f"[OK] Organization exists: {organizations[0]['name']} (ID: {org_id})")
        
        if not org_id:
            click.echo("[ERROR] Failed to create or find organization", err=True)
            return False, False
        
        # Check for apps
        apps = await db_provider.fetch_all("SELECT app_id, name FROM apps LIMIT 1")
        app_created = False
        
        if not apps:
            # Create default CLI app
            app_name = get_cli_app_name()
            app_description = get_cli_app_description()
            
            if verbose:
                click.echo(f"Creating default app: {app_name}")
            
            await db_provider.execute(
                """INSERT INTO apps (app_id, app_slug, name, description, version, creator_user_id) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                CLI_APP_UUID, CLI_APP_SLUG, app_name, app_description, CLI_APP_VERSION, user_id
            )
            
            if verbose:
                click.echo(f"[OK] Created app: {app_name} (ID: {CLI_APP_UUID})")
        else:
            if verbose:
                click.echo(f"[OK] App exists: {apps[0]['name']} (ID: {apps[0]['app_id']})")
        
        # Create default API key for CLI usage if user was just created OR if forced
        if user_created or force_api_key:
            await _create_default_api_key(db_provider, user_id, org_id, verbose)
        
        return True, True
        
    except Exception as e:
        click.echo(f"[ERROR] Error ensuring user/app: {e}", err=True)
        return False, False

@click.command()
@click.option('--port', default=8000, help='Port to run on')
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--reload', is_flag=True, help='Enable auto-reload for development')
@click.option('--no-browser', is_flag=True, help='Disable automatic browser opening')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.option('--dev', is_flag=True, help='Development mode with auto-reload and Vite integration')
@click.option('--worker', is_flag=True, help='Enable background worker for processing activations')
@click.option('--vite-port', default=5556, help='Port for Vite dev server (development mode only)')
@click.option('--with-frontend', is_flag=True, 
              help='Serve frontend assets (auto-enabled by default)')
@click.option('--frontend-path', 
              help='Path to frontend assets (auto-detected if not provided)')
@click.option('--database-url', 
              help='Database URL (defaults to sqlite:///./fiberwise.db)')
@click.option('--app', help='Custom ASGI application to run')
def start(port: int, host: str, reload: bool, no_browser: bool, verbose: bool, dev: bool, 
          worker: bool, vite_port: int, with_frontend: bool, frontend_path: str, database_url: str, app: str):
    """
    Start the FiberWise web server with production or development mode.
    
    This command initializes the database (if needed), creates default user and app,
    and starts a web server for the FiberWise application using uvicorn.
    
    By default, runs in PRODUCTION mode with built static assets.
    The --dev flag enables development mode with:
    - Auto-reload for Python changes
    - Vite integration for frontend development
    - Enhanced debugging output
    
    The --worker flag enables background activation processing for:
    - Chat functionality
    - Agent activation processing
    - Real-time responses
    
    Examples:
        fiber start                                    # Production mode with built assets
        fiber start --dev                             # Development mode with Vite dev server
        fiber start --worker                          # Production mode with background worker
        fiber start --dev --worker                    # Development mode with worker and Vite
        fiber start --port 3000                       # Custom port in production mode
        fiber start --dev --port 3000 --vite-port 3001 # Custom ports for both servers
        fiber start --database-url postgresql://...   # Custom database
        fiber start --verbose                         # Show database initialization details
    """
    # Check if fiberwise is properly initialized before starting
    is_initialized, init_message = check_fiberwise_initialized()
    if not is_initialized:
        click.echo(f"❌ {init_message}", err=True)
        click.echo("", err=True)
        click.echo("To fix this, run:", err=True)
        click.echo("  fiber initialize", err=True)
        click.echo("", err=True)
        click.echo("This will set up the web components and download required files.", err=True)
        sys.exit(1)
    
    config = Config()
    url = f"http://{host}:{port}"
    
    # Handle --dev flag (sets development mode defaults)
    if dev:
        reload = False
        verbose = True
        mode = 'dev'
        if verbose:
            click.echo("🚀 Development mode enabled (--dev)")
    
    # Initialize database using common migration system (same as activate command)
    async def init_database():
        if not await _run_common_migrations_and_setup(config, verbose):
            click.echo("Failed to initialize database", err=True)
            sys.exit(1)
    
    # Run database initialization
    try:
        if verbose:
            click.echo("Initializing database and seeding default user/app...")
        asyncio.run(init_database())
        if verbose:
            click.echo("Database initialization completed successfully")
    except Exception as e:
        click.echo(f"Error during database initialization: {e}", err=True)
        sys.exit(1)
    
    # Validate port range
    if not (1 <= port <= 65535):
        click.echo(f"Error: Port {port} is not valid. Must be between 1 and 65535.", err=True)
        sys.exit(1)
    
    # Check if port is available before starting
    if not check_port_available(host, port):
        click.echo(f"Error: Port {port} is already in use on {host}.", err=True)
        click.echo(f"Try using a different port with --port option.", err=True)
        sys.exit(1)
    
    # Development mode setup
    if dev:
        success = _setup_development_mode(verbose, port, vite_port)
        if not success:
            click.echo("⚠️  Development mode setup had issues, continuing anyway...")
        reload = False  # Force reload in dev mode
    
    # Determine application to run (always use standalone app)
    if app:
        app_to_run = app
    else:
        app_to_run = 'fiberwise.web.main:app'
    
    # Set up environment variables
    os.environ['FIBERWISE_MODE'] = 'development' if dev else 'production'
    if database_url:
        os.environ['DATABASE_URL'] = database_url
    
    # Configure worker settings
    if worker:
        # Enable integrated worker for in-process activation processing
        os.environ['WORKER_ENABLED'] = 'true'
        click.echo("🔧 Background worker: ENABLED (integrated)")
        click.echo("   • Activation processing")
        click.echo("   • Chat functionality")
    else:
        os.environ['WORKER_ENABLED'] = 'false'
        if verbose:
            click.echo("🔧 Background worker: DISABLED")
            click.echo("   • Use --worker flag to enable")
    
    # Set Vite configuration for development mode
    if dev:
        os.environ['VITE_DEV_PORT'] = str(vite_port)
        os.environ['VITE_API_TARGET'] = f'http://{host}:{port}'
    
    # Handle frontend serving - always enable by default
    if with_frontend or True:  # Always serve frontend by default
        if not frontend_path:
            core_web_path = find_core_web_path()
            if core_web_path:
                if dev:
                    # In dev mode, serve from web directory (source files)
                    frontend_path = str(core_web_path)
                    click.echo(f"Development mode: serving from source files at {frontend_path}")
                else:
                    # In production mode, serve from static (built files)
                    static_path = core_web_path / "static"
                    if static_path.exists():
                        frontend_path = str(static_path)
                        click.echo(f"Production mode: serving built assets from {frontend_path}")
                    else:
                        # Fallback to source files if no build exists
                        frontend_path = str(core_web_path)
                        click.echo(f"Warning: No built assets found, serving from source files at {frontend_path}")
                        click.echo("Run 'fiber initialize' to set up web components properly")
            else:
                click.echo("Warning: fiberwise web directory not found, frontend will not be available")
                click.echo("Run 'fiber initialize' to set up web components")
        
        if frontend_path:
            os.environ['SERVE_FRONTEND'] = 'true'
            os.environ['FRONTEND_PATH'] = frontend_path
    
    mode_display = "development" if dev else "production"
    click.echo(f"Starting FiberWise web server in {mode_display} mode...")
    click.echo(f"Server URL: {url}")
    click.echo(f"Application: {app_to_run}")
    
    if reload:
        click.echo("Development mode: Auto-reload enabled")
    
    try:
        # Check if the app module can be imported
        try:
            app_module, app_name = app_to_run.split(':')
            __import__(app_module)
        except (ImportError, ValueError) as e:
            click.echo(f"Error: Cannot import application '{app_to_run}': {e}", err=True)
            click.echo("Make sure the application module exists and is in the Python path.", err=True)
            
            # Provide helpful suggestions
            click.echo("\nEnsure fiberwise package is properly installed and fiberwise-core-web is available.", err=True)
                
            sys.exit(1)
        
        # Start browser opening thread if requested
        if not no_browser:
            click.echo("Browser will open automatically in 1.5 seconds...")
            open_browser_delayed(host, port)
        
        # Start background worker if requested
        if worker:
            click.echo("🔧 Starting background worker...")
            worker_success = start_background_worker(verbose)
            if worker_success:
                click.echo("✅ Background worker started")
            else:
                click.echo("⚠️  Background worker failed to start, continuing without it")
        
        # Start the server with appropriate configuration
        uvicorn_config = {
            "app": app_to_run,
            "host": host,
            "port": port,
            "access_log": True
        }
        
        # Configure logging based on mode
        if dev or verbose:
            uvicorn_config["log_level"] = "debug"
        else:
            uvicorn_config["log_level"] = "info"
        
        if reload:
            uvicorn_config["reload"] = True
            # Add reload directories if in dev mode
            if dev:
                reload_dirs = []
                # Add common reload directories
                for dir_name in ["fiberwise", "fiberwise_common", "fiberwise_core"]:
                    if Path(dir_name).exists():
                        reload_dirs.append(dir_name)
                
                # Add frontend path if specified
                if frontend_path and Path(frontend_path).exists():
                    reload_dirs.append(frontend_path)
                
                # Add core-web path if found
                core_web_path = find_core_web_path()
                if core_web_path:
                    reload_dirs.append(str(core_web_path))
                
                if reload_dirs:
                    uvicorn_config["reload_dirs"] = reload_dirs
                    if verbose:
                        click.echo(f"Watching directories for changes: {reload_dirs}")
        
        # Development mode specific configuration
        if dev:
            if verbose:
                click.echo("🚀 Starting in development mode with enhanced features")
                if hasattr(_start_vite_dev_server, '_vite_process'):
                    click.echo("📁 Frontend dev server: http://localhost:5173")
                click.echo(f"🌐 API server: http://{host}:{port}")
        
        # Start uvicorn server
        click.echo(f"Starting FiberWise server on {url}")
        uvicorn.run(**uvicorn_config)
        
    except OSError as e:
        # Stop worker on error
        if worker:
            stop_background_worker(verbose)
        
        if "Address already in use" in str(e) or "WinError 10048" in str(e):
            click.echo(f"Error: Port {port} is already in use.", err=True)
            click.echo(f"Try using a different port with --port option.", err=True)
        elif "Permission denied" in str(e):
            click.echo(f"Error: Permission denied to bind to {host}:{port}", err=True)
            if port < 1024:
                click.echo(f"Ports below 1024 require administrator privileges.", err=True)
        else:
            click.echo(f"Error: Cannot bind to {host}:{port}: {e}", err=True)
        sys.exit(1)
        
    except KeyboardInterrupt:
        click.echo("\nServer shutdown requested by user.")
        if worker:
            click.echo("🛑 Stopping background worker...")
            stop_background_worker(verbose)
        sys.exit(0)
        
    except Exception as e:
        # Stop worker on any error
        if worker:
            stop_background_worker(verbose)
        click.echo(f"Error: Failed to start server: {e}", err=True)
        sys.exit(1)
