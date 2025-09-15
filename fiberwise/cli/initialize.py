import click
import asyncio
import sys
import subprocess
import os
import shutil
import secrets
from pathlib import Path
from datetime import datetime
from fiberwise_common.entities.config import Config
from fiberwise_common.constants import (
    CLI_APP_UUID, 
    CLI_APP_SLUG,
    get_cli_app_name, 
    get_cli_app_description,
    get_cli_user_email,
    CLI_APP_VERSION
)# Import from start_enhanced for shared functionality
from .start_enhanced import _run_common_migrations_and_setup, _ensure_default_user_and_app

@click.command()
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.option('--database-url', 
              help='Database URL (defaults to sqlite://~/.fiberwise/fiberwise.db)')
@click.option('--skip-web', is_flag=True, help='Skip web component initialization')
@click.option('--force', is_flag=True, help='Force re-initialization even if already initialized')
@click.option('--force-clone', is_flag=True, help='Force cloning from GitHub instead of using local directory')
def setup(verbose: bool, database_url: str, skip_web: bool, force: bool, force_clone: bool):
    """
    Setup FiberWise database and web components.
    
    This command sets up the complete FiberWise environment by:
    1. Creating the database and applying migrations
    2. Setting up default user and application
    3. Initializing web components (fiberwise-core-web)
    4. Installing frontend dependencies
    5. Building frontend assets
    
    Examples:
        fiber setup                    # Setup everything
        fiber setup --verbose         # Show detailed progress
        fiber setup --skip-web        # Skip web component setup
        fiber setup --force           # Force re-setup
    """
    if verbose:
        click.echo("🚀 Initializing FiberWise platform...")
    
    # Step 0: Setup storage configuration
    if verbose:
        click.echo("\n📁 Step 0: Storage Configuration Setup")
    
    if not _setup_storage_configuration(verbose):
        click.echo("❌ Storage configuration setup failed", err=True)
        sys.exit(1)
    
    # Step 1: Initialize database and core components
    if verbose:
        click.echo("\n📋 Step 1: Database and Core Setup")
    
    config = Config()
    if database_url:
        # Override database URL if provided
        config.database_url = database_url
    
    # Initialize database using common migration system
    async def init_database():
        if not await _run_common_migrations_and_setup(config, verbose):
            click.echo("❌ Database initialization failed", err=True)
            return False
        return True
    
    # Run database initialization
    try:
        if verbose:
            click.echo("   Initializing database and seeding default user/app...")
        
        success = asyncio.run(init_database())
        if not success:
            sys.exit(1)
            
        if verbose:
            click.echo("   ✅ Database initialization completed successfully")
    except Exception as e:
        click.echo(f"❌ Error during database initialization: {e}", err=True)
        sys.exit(1)
    
    # Step 2: Web components initialization
    if not skip_web:
        if verbose:
            click.echo("\n🌐 Step 2: Web Components Setup")
        
        success = _initialize_web_components(verbose, force, force_clone)
        if not success:
            click.echo("❌ Web components initialization failed", err=True)
            sys.exit(1)
    
    # Final success message
    click.echo("\n🎉 FiberWise setup completed successfully!")
    click.echo("\nNext steps:")
    click.echo("  📈 Start development server: fiber start --dev")
    click.echo("  🌐 Start production server: fiber start")
    click.echo("  📚 View documentation: Open browser to http://localhost:8000 after starting")


@click.command()
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.option('--core', is_flag=True, help='Also remove core web components (more thorough cleanup)')
def clean(verbose: bool, core: bool):
    """
    Clean up files and directories created by fiber setup.
    
    This command removes:
    1. ~/.fiberwise directory and all contents
    2. Core web components (only with --core flag)
    
    Note: This command will fail if any files are currently in use.
    Stop all running fiber processes before cleaning.
    
    Examples:
        fiber clean                       # Clean ~/.fiberwise directory
        fiber clean --core                # Also remove core web components  
        fiber clean --verbose             # Show detailed cleanup progress
    """
    if verbose:
        click.echo("🧹 Cleaning up FiberWise setup files...")
    
    # First, check if any processes might be using the files
    home_fiberwise_dir = Path.home() / ".fiberwise"
    if home_fiberwise_dir.exists():
        db_file = home_fiberwise_dir / "fiberwise.db"
        if db_file.exists():
            try:
                # Try to open the database file to check if it's locked
                with open(db_file, 'r+b') as f:
                    pass  # Just checking if we can access it
            except PermissionError:
                click.echo("❌ Error: Database file is currently in use.", err=True)
                click.echo("💡 Please stop all running 'fiber start' processes and try again.", err=True)
                return
            except Exception as e:
                if verbose:
                    click.echo(f"⚠️  Could not check database file status: {e}")
    
    items_to_clean = []
    
    # 1. ~/.fiberwise directory
    if home_fiberwise_dir.exists():
        items_to_clean.append(("FiberWise home directory", home_fiberwise_dir))
    
    # 2. Core web components in pip package (only with --core flag)
    if core:
        try:
            import importlib.util
            spec = importlib.util.find_spec('fiberwise')
            
            if spec and spec.origin:
                package_dir = Path(spec.origin).parent
            elif spec and spec.submodule_search_locations:
                search_locations = list(spec.submodule_search_locations)
                if search_locations:
                    package_dir = Path(search_locations[0])
                else:
                    package_dir = None
            else:
                package_dir = None
            
            if package_dir:
                web_dir = package_dir / "web"
                if web_dir.exists():
                    items_to_clean.append(("Core web components", web_dir))
        except Exception as e:
            if verbose:
                click.echo(f"   ⚠️  Could not locate package web directory: {e}")
    
    if not items_to_clean:
        click.echo("✅ No setup files found to clean")
        return
    
    # Show what will be cleaned
    if verbose:
        click.echo("\n📋 Items to be cleaned:")
        for description, path in items_to_clean:
            click.echo(f"   • {description}: {path}")
        click.echo()
    
    # Always confirm cleanup
    if not click.confirm("Are you sure you want to remove all these items?"):
        click.echo("Cleanup cancelled")
        return
    
    # Perform cleanup
    for description, path in items_to_clean:
        try:
            if verbose:
                click.echo(f"   🗑️  Removing {description}: {path}")
            
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                import shutil
                shutil.rmtree(path)
            
            if verbose:
                click.echo(f"   ✅ Removed {description}")
                
        except PermissionError as e:
            click.echo(f"❌ Error: Cannot remove {description} - file is in use", err=True)
            click.echo("💡 Please stop all running 'fiber start' processes and try again.", err=True)
            return
        except Exception as e:
            click.echo(f"❌ Error removing {description}: {e}", err=True)
            return
    
    # Success
    click.echo("\n🎉 Cleanup completed successfully!")
        
    if verbose:
        click.echo("\n💡 To set up FiberWise again, run: fiber setup")


def _setup_local_configuration(verbose: bool) -> bool:
    """
    Setup local configuration for FiberWise CLI.
    Creates local.json config with proper API key and sets it as default.
    """
    try:
        from pathlib import Path
        import json
        
        # Get paths
        home_dir = Path.home()
        fiberwise_dir = home_dir / ".fiberwise"
        configs_dir = fiberwise_dir / "configs"
        
        # Create configs directory
        configs_dir.mkdir(parents=True, exist_ok=True)
        
        # Get the API key that was created during database setup
        # This should match the logic from the database initialization
        api_key = None
        try:
            # Try to get the API key from the database
            from fiberwise_common.entities.config import Config
            config = Config()
            
            # Initialize database connection
            import asyncio
            
            async def get_api_key():
                try:
                    await config.db_manager.initialize()
                    
                    # Get the user's API key (should have been created during setup)
                    result = await config.db_provider.fetch_one(
                        "SELECT api_key FROM api_keys WHERE user_id = 1 AND is_active = 1 LIMIT 1"
                    )
                    
                    if result:
                        return result['api_key']
                    else:
                        # Create a new API key if none exists
                        import secrets
                        new_api_key = f"fw_{secrets.token_urlsafe(32)}"
                        
                        await config.db_provider.execute(
                            """INSERT INTO api_keys (user_id, api_key, name, scopes, is_active, created_at) 
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            1, new_api_key, "Default CLI API Key", "read,write", 1, datetime.now()
                        )
                        
                        if verbose:
                            click.echo(f"   ✅ Created new API key for local configuration")
                        
                        return new_api_key
                        
                except Exception as e:
                    if verbose:
                        click.echo(f"   ⚠️  Could not get/create API key from database: {e}")
                    return None
            
            api_key = asyncio.run(get_api_key())
            
        except Exception as e:
            if verbose:
                click.echo(f"   ⚠️  Could not access database for API key: {e}")
        
        # Fallback to a reasonable default if we couldn't get from database
        if not api_key:
            api_key = "fiber-platform-api-key"
            if verbose:
                click.echo(f"   ⚠️  Using fallback API key - you may need to update this later")
        
        # Create local configuration
        config_data = {
            "name": "local",
            "api_key": api_key,
            "base_url": "http://localhost:8000",
            "created_at": str(datetime.now()),
            "updated_at": str(datetime.now())
        }
        
        # Save local config
        local_config_file = configs_dir / "local.json"
        with open(local_config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)
        
        if verbose:
            click.echo(f"   ✅ Created local configuration: {local_config_file}")
            if api_key != "fiber-platform-api-key":
                click.echo(f"   🔑 Using API key: {api_key[:12]}...")
        
        # Set as default configuration
        default_file = fiberwise_dir / "default_config.txt"
        with open(default_file, 'w', encoding='utf-8') as f:
            f.write("local")
        
        if verbose:
            click.echo(f"   ✅ Set 'local' as default configuration")
            click.echo(f"   📋 Configuration ready for --to-instance commands")
        
        return True
        
    except Exception as e:
        if verbose:
            click.echo(f"   ❌ Error setting up local configuration: {e}")
        return False


def _clone_repository(url: str, target_path: Path, verbose: bool) -> bool:
    """Clone a git repository to the specified path."""
    try:
        if verbose:
            click.echo(f"   Cloning {url} to {target_path}...")
        
        # Check if git is available
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            if verbose:
                click.echo("   ⚠️  Git not found, unable to clone repository")
            return False
        
        # Clone the repository
        result = subprocess.run(
            ["git", "clone", url, str(target_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        if result.returncode != 0:
            if verbose:
                click.echo(f"   ❌ Git clone failed: {result.stderr}")
            return False
        
        # Verify clone was successful
        if not target_path.exists() or not (target_path / ".git").exists():
            if verbose:
                click.echo("   ❌ Clone verification failed")
            return False
        
        return True
        
    except subprocess.TimeoutExpired:
        if verbose:
            click.echo("   ❌ Git clone timed out")
        return False
    except Exception as e:
        if verbose:
            click.echo(f"   ❌ Error during git clone: {e}")
        return False


def _initialize_web_components(verbose: bool, force: bool, force_clone: bool = False) -> bool:
    """Initialize web components by cloning fiberwise-core-web to the pip package web folder."""
    try:
        # Get the pip package directory - handle editable installs properly
        import importlib.util
        
        # Use the modern importlib approach to find package path
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
                raise ImportError("No search locations found for fiberwise package")
        else:
            # Fallback: try importing and using __file__ if available
            try:
                import fiberwise
                if hasattr(fiberwise, '__file__') and fiberwise.__file__:
                    package_dir = Path(fiberwise.__file__).parent
                else:
                    raise ImportError("Cannot determine package location")
            except:
                if verbose:
                    click.echo("   ❌ Could not determine fiberwise package location")
                return False
        
        web_dir = package_dir / "web"
        
        if verbose:
            click.echo(f"   Package directory: {package_dir}")
            click.echo(f"   Target web directory: {web_dir}")
        
        # Create package directory if it doesn't exist
        package_dir.mkdir(parents=True, exist_ok=True)
        
        # Remove existing web directory if force or force_clone
        if (force or force_clone) and web_dir.exists():
            if verbose:
                click.echo(f"   🗑️  Removing existing web directory...")
            shutil.rmtree(web_dir)
        
        # Clone repository directly to web directory
        if not web_dir.exists() or force_clone:
            if verbose:
                click.echo("   🔄 Cloning fiberwise-core-web from GitHub to pip package...")
            
            if _clone_repository(
                url="https://github.com/fiberwise-ai/fiberwise-core-web.git",
                target_path=web_dir,
                verbose=verbose
            ):
                if verbose:
                    click.echo(f"   ✅ Successfully cloned fiberwise-core-web to: {web_dir}")
            else:
                if verbose:
                    click.echo("   ❌ Failed to clone fiberwise-core-web repository")
                return False
        else:
            if verbose:
                click.echo(f"   ✅ Web directory already exists at: {web_dir}")
        
        # Configure for home directory usage
        if verbose:
            click.echo("   ⚙️  Configuring for home directory usage...")
        
        if not _configure_core_web_for_home_dir(web_dir, verbose):
            if verbose:
                click.echo("   ⚠️  Configuration failed, but continuing...")
        elif verbose:
            click.echo("   ✅ Configuration completed")
        
        # Install Node.js dependencies if package.json exists
        package_json = web_dir / "package.json"
        if package_json.exists():
            if verbose:
                click.echo("   📦 Installing Node.js dependencies (root)...")
            else:
                click.echo("📦 Installing Node.js dependencies...")
            
            try:
                # Try to find npm in PATH or use common locations
                npm_cmd = "npm"
                try:
                    # Test if npm is accessible
                    subprocess.run([npm_cmd, "--version"], capture_output=True, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Try common npm locations on Windows
                    possible_npm_paths = [
                        "C:\\Program Files\\nodejs\\npm.cmd",
                        "C:\\Program Files (x86)\\nodejs\\npm.cmd",
                        os.path.expanduser("~\\AppData\\Roaming\\npm\\npm.cmd")
                    ]
                    for npm_path in possible_npm_paths:
                        if os.path.exists(npm_path):
                            npm_cmd = npm_path
                            break
                    else:
                        raise FileNotFoundError("npm not found")
                
                result = subprocess.run(
                    [npm_cmd, "install"],
                    cwd=web_dir,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minutes timeout
                    env=dict(os.environ)  # Inherit full environment
                )
                
                if result.returncode != 0:
                    if verbose:
                        click.echo(f"   ⚠️  npm install failed: {result.stderr}")
                        click.echo("   Continuing without Node.js dependencies...")
                else:
                    if verbose:
                        click.echo("   ✅ Node.js dependencies installed (root)")
                    else:
                        click.echo("✅ Node.js dependencies installed")
                        
            except subprocess.TimeoutExpired:
                click.echo("   ❌ npm install timed out")
                return False
            except FileNotFoundError:
                if verbose:
                    click.echo("   ⚠️  npm not found, skipping dependency installation")
        
        # Install frontend dependencies if fiberwise_core/package.json exists
        frontend_package_json = web_dir / "fiberwise_core" / "package.json"
        if frontend_package_json.exists():
            if verbose:
                click.echo("   📦 Installing frontend dependencies...")
            else:
                click.echo("📦 Installing frontend dependencies...")
            
            try:
                # Try to find npm in PATH or use common locations
                npm_cmd = "npm"
                try:
                    # Test if npm is accessible
                    subprocess.run([npm_cmd, "--version"], capture_output=True, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Try common npm locations on Windows
                    possible_npm_paths = [
                        "C:\\Program Files\\nodejs\\npm.cmd",
                        "C:\\Program Files (x86)\\nodejs\\npm.cmd",
                        os.path.expanduser("~\\AppData\\Roaming\\npm\\npm.cmd")
                    ]
                    for npm_path in possible_npm_paths:
                        if os.path.exists(npm_path):
                            npm_cmd = npm_path
                            break
                    else:
                        raise FileNotFoundError("npm not found")
                
                result = subprocess.run(
                    [npm_cmd, "install"],
                    cwd=web_dir / "fiberwise_core",
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minutes timeout
                    env=dict(os.environ)  # Inherit full environment
                )
                
                if result.returncode != 0:
                    if verbose:
                        click.echo(f"   ⚠️  Frontend npm install failed: {result.stderr}")
                        click.echo("   Continuing without frontend dependencies...")
                else:
                    if verbose:
                        click.echo("   ✅ Frontend dependencies installed")
                    else:
                        click.echo("✅ Frontend dependencies installed")
                        
            except subprocess.TimeoutExpired:
                click.echo("   ❌ Frontend npm install timed out")
                return False
            except FileNotFoundError:
                if verbose:
                    click.echo("   ⚠️  npm not found, skipping frontend dependency installation")
        
        if verbose:
            click.echo("   ✅ Web components initialization completed")
        
        return True
        
    except Exception as e:
        click.echo(f"   ❌ Error during web components initialization: {e}", err=True)
        return False


def _check_system_requirements(verbose: bool) -> bool:
    """Check if system requirements are met."""
    if verbose:
        click.echo("   🔍 Checking system requirements...")
    
    # Check for Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            if verbose:
                click.echo(f"   ✅ Node.js found: {result.stdout.strip()}")
        else:
            if verbose:
                click.echo("   ⚠️  Node.js not found")
            return False
    except FileNotFoundError:
        if verbose:
            click.echo("   ⚠️  Node.js not found")
        return False
    
    # Check for npm
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            if verbose:
                click.echo(f"   ✅ npm found: {result.stdout.strip()}")
        else:
            if verbose:
                click.echo("   ⚠️  npm not found")
    except FileNotFoundError:
        if verbose:
            click.echo("   ⚠️  npm not found")
    
    return True


def _configure_core_web_for_home_dir(core_web_path: Path, verbose: bool) -> bool:
    """
    Configure fiberwise-core-web to use home directory settings when run via fiber CLI.
    Creates a .env.fiber file that will be used by the fiber CLI.
    """
    try:
        from pathlib import Path
        
        # Get user home directory and .fiberwise path
        home_dir = Path.home()
        fiberwise_dir = home_dir / ".fiberwise"
        
        # Create .env.fiber file for fiber CLI usage
        env_fiber_file = core_web_path / ".env.fiber"
        env_content = f"""# FiberWise Core Web configuration for use with fiber CLI
# This file is used when FIBERWISE_USE_HOME_DIR=true

# Flag to use home directory
FIBERWISE_USE_HOME_DIR=true

# Environment settings
ENVIRONMENT=development
DEBUG=false

# Database configuration (uses home directory)
DB_PROVIDER=sqlite
DATABASE_URL=sqlite:///{str(fiberwise_dir / 'fiberwise.db').replace(chr(92), '/')}

# Storage provider (home directory)
STORAGE_PROVIDER=local
UPLOADS_DIR={str(fiberwise_dir / 'uploads').replace(chr(92), '/')}
APP_BUNDLES_DIR={str(fiberwise_dir / 'app_bundles' / 'apps').replace(chr(92), '/')}
ENTITY_BUNDLES_DIR={str(fiberwise_dir / 'entity_bundles').replace(chr(92), '/')}

# Server settings
BASE_URL=http://localhost:8000
PORT=8000
HOST=0.0.0.0

# Security
SECRET_KEY=fiber-cli-secret-key-change-in-production

# Worker settings
WORKER_ENABLED=false

# API settings
API_PREFIX=/api/v1

# CORS settings
CORS_ORIGINS=["http://localhost:8000", "http://localhost:3000", "http://localhost:5556"]

# Project settings
PROJECT_NAME=FiberWise Platform
VERSION=0.0.1

# Fiber API settings
FIBER_API_BASE_URL=http://localhost:8000/api/v1
FIBER_API_KEY=fiber-platform-api-key

# Platform settings
PLATFORM_BASE_URL=http://localhost:8000
"""
        
        with open(env_fiber_file, 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        if verbose:
            click.echo(f"   ✅ Created fiber CLI environment: {env_fiber_file}")
        
        return True
        
    except Exception as e:
        if verbose:
            click.echo(f"   ❌ Error configuring core-web for home directory: {e}")
        return False


def _setup_storage_configuration(verbose: bool) -> bool:
    """
    Setup storage configuration for FiberWise.
    Creates ~/.fiberwise directory structure and configuration files.
    """
    try:
        # Get user home directory and .fiberwise path
        home_dir = Path.home()
        fiberwise_dir = home_dir / ".fiberwise"
        
        # Create .fiberwise directory if it doesn't exist
        fiberwise_dir.mkdir(exist_ok=True)
        if verbose:
            click.echo(f"   ✅ Created/verified .fiberwise directory: {fiberwise_dir}")
        
        # Create storage subdirectories
        storage_dirs = [
            fiberwise_dir / "app_uploads",
            fiberwise_dir / "app_bundles" / "apps", 
            fiberwise_dir / "entity_bundles",
            fiberwise_dir / "agent_storage"
        ]
        
        for storage_dir in storage_dirs:
            storage_dir.mkdir(parents=True, exist_ok=True)
            if verbose:
                click.echo(f"   ✅ Created storage directory: {storage_dir}")
        
        # Create .env file in .fiberwise directory if it doesn't exist
        env_file = fiberwise_dir / ".env"
        if not env_file.exists():
            env_content = f"""# FiberWise Storage Configuration
# Generated by fiber initialize command

# Storage Provider Configuration
STORAGE_PROVIDER=local
UPLOADS_DIR={fiberwise_dir / "app_uploads"}
APP_BUNDLES_DIR={fiberwise_dir / "app_bundles" / "apps"}
ENTITY_BUNDLES_DIR={fiberwise_dir / "entity_bundles"}

# Database Configuration
DATABASE_URL=sqlite:///{fiberwise_dir / "fiberwise.db"}

# Local Storage Settings
FIBERWISE_HOME={fiberwise_dir}
FIBERWISE_DB_PATH={fiberwise_dir / "fiberwise.db"}

# Default settings for local development
ENVIRONMENT=development
DEBUG=false
BASE_URL=http://localhost:8000
"""
            
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(env_content)
            if verbose:
                click.echo(f"   ✅ Created environment configuration: {env_file}")
        elif verbose:
            click.echo(f"   ✓ Environment configuration exists: {env_file}")
        
        # Create a settings.json file for additional configuration
        settings_file = fiberwise_dir / "settings.json"
        if not settings_file.exists():
            # Convert Windows paths to forward slashes for JSON
            settings_content = f"""{{
    "storage": {{
        "provider": "local",
        "base_path": "{str(fiberwise_dir).replace(chr(92), '/')}",
        "uploads_dir": "{str(fiberwise_dir / 'app_uploads').replace(chr(92), '/')}",
        "app_bundles_dir": "{str(fiberwise_dir / 'app_bundles' / 'apps').replace(chr(92), '/')}",
        "entity_bundles_dir": "{str(fiberwise_dir / 'entity_bundles').replace(chr(92), '/')}",
        "agent_storage_dir": "{str(fiberwise_dir / 'agent_storage').replace(chr(92), '/')}"
    }},
    "database": {{
        "provider": "sqlite",
        "url": "sqlite:///{str(fiberwise_dir / 'fiberwise.db').replace(chr(92), '/')}",
        "path": "{str(fiberwise_dir / 'fiberwise.db').replace(chr(92), '/')}"
    }},
    "environment": "development",
    "initialized": true
}}"""
            
            with open(settings_file, 'w', encoding='utf-8') as f:
                f.write(settings_content)
            if verbose:
                click.echo(f"   ✅ Created settings configuration: {settings_file}")
        elif verbose:
            click.echo(f"   ✓ Settings configuration exists: {settings_file}")
        
        if verbose:
            click.echo(f"   🎉 Storage configuration setup completed")
            click.echo(f"   📁 Configuration location: {fiberwise_dir}")
            click.echo(f"   🗄️  Database location: {fiberwise_dir / 'fiberwise.db'}")
            click.echo(f"   📦 App bundles location: {fiberwise_dir / 'app_bundles' / 'apps'}")
        
        return True
        
    except Exception as e:
        if verbose:
            click.echo(f"   ❌ Error setting up storage configuration: {e}")
        return False
