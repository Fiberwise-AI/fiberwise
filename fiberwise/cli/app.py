"""
App management commands for FiberWise CLI.
"""
import click
import os
import json
import requests
import tempfile
import subprocess
import signal
import yaml
import threading
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
import sys
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError as e:
    WATCHDOG_AVAILABLE = False
    WATCHDOG_IMPORT_ERROR = str(e)

# Add fiberwise-common to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "fiberwise-common"))

# Import shared utilities from fiberwise-common
from fiberwise_common.services.fiber_app_manager import (
    FiberAppManager, 
    AppOperationResult,
    validate_instance_config,
    get_default_instance_config,
    load_instance_config
)
from .app_utils import (
    update_manifest_version, 
    find_manifest_file, 
    load_manifest,
    save_instance_app_info,
    load_instance_app_info,
    FIBER_DATA_DIR,
    APP_INFO_FILE
)
from .app_context import AppOperationContext
from .core_commands import deploy, update
from .oauth_commands import oauth




@click.group(name='app')
def app():
    """Manage FiberWise applications."""
    pass

# Add imported commands
app.add_command(deploy)
app.add_command(update)
app.add_command(oauth)





@app.command(name='info')
@click.argument('app_path', type=click.Path(exists=True, path_type=Path), default='.')
@click.option('--to-instance', help='Target specific config instance by name')
@click.option('--verbose', is_flag=True, help='Show detailed information')
def show_info(app_path: Path, to_instance: Optional[str], verbose: bool):
    """Show information about the current app.
    
    APP_PATH: Path to the directory containing the app (default: current directory)
    """
    try:
        # Initialize centralized context - handles ALL instance resolution and config loading
        ctx = AppOperationContext(app_path, to_instance, None, verbose)
        
        # Load manifest info
        manifest_version = "Unknown"
        app_name = "Unknown"
        
        if ctx.manifest_path:
            try:
                manifest_version = ctx.manifest_data.get('app', {}).get('version', 'Unknown')
                app_name = ctx.manifest_data.get('app', {}).get('name', 'Unknown')
            except Exception as e:
                if verbose:
                    click.echo(f"⚠️  Could not load manifest: {e}")
        
        click.echo(f"📱 App Information")
        click.echo("-" * 40)
        click.echo(f"Name: {app_name}")
        click.echo(f"Current Version: {manifest_version}")
        click.echo(f"App Directory: {app_path.absolute()}")
        click.echo(f"Instance: {ctx.instance_name}")
        
        if ctx.manifest_path:
            click.echo(f"Manifest File: {ctx.manifest_path.name}")
        
        if ctx.app_info:
            if ctx.app_info.get('app_id'):
                click.echo(f"App ID: {ctx.app_info['app_id']}")
            if ctx.app_info.get('app_version_id'):
                click.echo(f"Version ID: {ctx.app_info['app_version_id']}")
            if ctx.app_info.get('last_operation'):
                click.echo(f"Last Operation: {ctx.app_info['last_operation']}")
            if ctx.app_info.get('last_operation_timestamp'):
                click.echo(f"Last Updated: {ctx.app_info['last_operation_timestamp']}")
        
        if verbose and ctx.config_data:
            click.echo(f"\n🌐 Instance Configuration:")
            click.echo("-" * 40)
            base_url = ctx.config_data.get('base_url', 'Unknown')
            click.echo(f"Base URL: {base_url}")
        
        if verbose and ctx.app_info:
            click.echo("\n🔧 Detailed App Info:")
            click.echo("-" * 40)
            for key, value in ctx.app_info.items():
                click.echo(f"{key}: {value}")
    
    except click.ClickException:
        # Context initialization failed, error already displayed
        return
    except Exception as e:
        click.echo(f"❌ Error getting app info: {e}", err=True)

@app.command()
@click.argument('app_path', type=click.Path(exists=True, path_type=Path), default='.')
@click.option('--to-instance', help='Target FiberWise instance config name (uses default if not specified)')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def build(app_path: Path, to_instance: str, verbose: bool):
    """Build the application and create/update instance-specific app.json file.
    
    This command will:
    1. Run npm build if package.json with build script exists
    2. Create bundle (same as install/update process)
    3. Create or update .fiber/{instance_name}/app.json with build info
    4. If app is already installed, fetch current app_id and version_id
    
    APP_PATH: Path to the directory containing the app to build
    """
    try:
        # Initialize centralized context - handles ALL instance resolution and config loading
        ctx = AppOperationContext(app_path, to_instance, None, verbose)
        
        if verbose:
            click.echo(f"Building app from: {app_path}")
        
        # Step 1: Check if package.json exists and run npm build
        click.echo("🔧 Building application...")
        
        # Import here to avoid circular imports
        # Create a temporary app manager for build operations (no API calls needed)
        temp_manager = FiberAppManager("http://localhost", "temp_key", "temp")
        build_result = temp_manager._build_app(app_path)
        
        if not build_result.success:
            click.echo(f"❌ Build failed: {build_result.message}", err=True)
            return
        
        click.echo(f"✅ {build_result.message}")
        
        # Step 2: Create bundle
        click.echo("📦 Creating application bundle...")
        bundle_result = temp_manager._create_app_bundle(app_path)
        
        if not bundle_result.success:
            click.echo(f"❌ Bundle creation failed: {bundle_result.message}", err=True)
            return
        
        bundle_path = Path(bundle_result.data["bundle_path"])
        files_count = bundle_result.data["files_count"]
        click.echo(f"✅ Bundle created successfully with {files_count} files")
        
        # Step 3: Create/update instance-specific app info using context
        click.echo("📄 Creating/updating instance-specific app info...")
        
        # Use instance name from context (already validated)
        instance_name = ctx.instance_name
        if verbose:
            click.echo(f"Using instance: {instance_name}")
        
        # Create instance-specific directory structure: .fiber/{instance}/app.json
        fiber_dir = app_path / FIBER_DATA_DIR
        instance_dir = fiber_dir / instance_name
        instance_dir.mkdir(parents=True, exist_ok=True)
        
        app_info_file = instance_dir / APP_INFO_FILE
        
        # Use existing app info from context or load it
        existing_app_info = ctx.app_info or {}
        if existing_app_info and verbose:
            click.echo(f"Loaded existing app info from .fiber/{instance_name}/app.json")
        
        # Use manifest data from context
        if ctx.manifest_path and ctx.manifest_data:
            app_name = ctx.manifest_data.get("app", {}).get("name") or ctx.manifest_data.get("app_name", "unknown-app")
            app_version = ctx.manifest_data.get("app", {}).get("version") or ctx.manifest_data.get("app_version", "1.0.0")
        else:
            app_name = app_path.name
            app_version = "1.0.0"
        
        # Get app_id and version_id from context
        app_id = ctx.get_app_id()
        app_version_id = existing_app_info.get("app_version_id")
        
        # If we have valid API config and existing app_id, verify it still exists on server
        if ctx.has_valid_api_config() and app_id:
            try:
                if verbose:
                    click.echo(f"🌐 Checking app status on instance: {instance_name}")
                
                # Use context's API configuration
                api_endpoint, api_key = ctx.get_api_config()
                
                if api_endpoint and api_key:
                    # Create real app manager to check current status
                    real_manager = FiberAppManager(api_endpoint, api_key, instance_name)
                    
                    # Note: This would need an API endpoint to get current app version
                    # For now, we'll keep the existing version_id
                    if verbose:
                        click.echo(f"✅ Using existing app_id: {app_id}")
                        if app_version_id:
                            click.echo(f"✅ Using existing app_version_id: {app_version_id}")
                else:
                    if verbose:
                        click.echo(f"⚠️  Invalid config for {instance_name}, using local app info only")
            except Exception as e:
                if verbose:
                    click.echo(f"⚠️  Could not check server status: {e}")
        
        # Create/update instance-specific app info structure
        app_info = {
            "app_id": app_id,  # Will be None until first install
            "app_version_id": app_version_id,  # Will be None until first install
            "last_manifest_version": app_version,
            "last_manifest_hash": existing_app_info.get("last_manifest_hash"),  # Preserve from previous installs
            "current_app_dir": str(app_path.resolve()),
            "manifest_path": str(ctx.manifest_path.resolve()) if ctx.manifest_path else None,
            "instance_name": instance_name,
            "build_info": {
                "last_build": datetime.now().isoformat(),
                "build_command": f"fiber app build --to-instance {instance_name}",
                "files_bundled": files_count
            }
        }
        
        # Preserve any existing fields we don't want to overwrite
        if existing_app_info:
            # Keep the original creation time if it exists
            if "created_at" in existing_app_info:
                app_info["created_at"] = existing_app_info["created_at"]
            # Update build count
            build_count = existing_app_info.get("build_info", {}).get("build_count", 0)
            app_info["build_info"]["build_count"] = build_count + 1
            
            if verbose:
                click.echo(f"📝 Updated existing app info (build #{build_count + 1})")
        else:
            app_info["created_at"] = datetime.now().isoformat()
            app_info["build_info"]["build_count"] = 1
            if verbose:
                click.echo("📝 Created new app info file")
        
        try:
            with open(app_info_file, 'w', encoding='utf-8') as f:
                json.dump(app_info, f, indent=2, ensure_ascii=False)
            
            click.echo(f"✅ App info saved to .fiber/{instance_name}/app.json")
            
            if verbose:
                click.echo(f"   App name: {app_name}")
                click.echo(f"   App version: {app_version}")
                click.echo(f"   Instance: {instance_name}")
            
            if not app_id:
                click.echo("   💡 app_id and app_version_id will be populated after first install")
                click.echo(f"   💡 Use: fiber app install . --to-instance {instance_name}")
            else:
                click.echo(f"   📋 App ID: {app_id}")
                if app_version_id:
                    click.echo(f"   📋 Version ID: {app_version_id}")
                    
        except Exception as e:
            click.echo(f"❌ Failed to save app info file: {e}", err=True)
        
        # Step 4: Clean up temporary bundle
        try:
            if bundle_path.exists():
                bundle_path.unlink()
                if verbose:
                    click.echo(f"🧹 Cleaned up temporary bundle: {bundle_path}")
        except Exception as e:
            if verbose:
                click.echo(f"Warning: Could not clean up bundle file: {e}")
        
        click.echo("🎉 Build completed successfully!")
        
        # Show next steps
        if not app_id:
            click.echo("\n📌 Next steps:")
            click.echo(f"   1. Install: fiber app install . --to-instance {instance_name}")
            click.echo(f"   2. Or Update: fiber app update . --to-instance {instance_name}")
    
    except Exception as e:
        click.echo(f"❌ Error during build: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)


def display_operation_result(result: AppOperationResult, operation_name: str):
    """Display the results of an app operation in a user-friendly format."""
    if result.success:
        click.echo(f"[SUCCESS] {result.message}")
        
        # Display info messages
        for info in result.info_messages:
            click.echo(f"   [INFO] {info}")
        
        # Display warnings  
        for warning in result.warnings:
            click.echo(f"   [WARNING] {warning}")
            
    else:
        click.echo(f"[ERROR] {operation_name} failed: {result.message}")
        
        # Handle specific suggestions
        if result.data.get("suggestion") == "update":
            click.echo("   [SUGGESTION] Use 'fiber app update .' to update the existing app")




@app.command()
@click.argument('app_path', type=click.Path(exists=True, path_type=Path), default='.')
@click.option('--to-instance', default='local', help='Target FiberWise instance: "local" for local development, or config name for remote API')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.option('--port', default=None, type=int, help='Port for npm dev server (default: from package.json or 5173)')
@click.option('--watch-python', is_flag=True, default=True, help='Watch Python files for changes (default: true)')
def dev(app_dir: str, to_instance: str, verbose: bool, port: Optional[int], watch_python: bool):
    """
    Start development mode for a FiberWise app.
    
    This command:
    1. Loads app configuration from .fiber/{instance}/app.json
    2. Runs npm dev for frontend development
    3. Watches Python files for changes (optional)
    4. Ensures the app is properly configured for development
    
    The app must be installed first (fiber app install .) to generate app_id and version_id.
    """
    import asyncio
    asyncio.run(_dev_async(app_dir, to_instance, verbose, port, watch_python))


async def _dev_async(app_dir: str, to_instance: str, verbose: bool, port: Optional[int], watch_python: bool):
    """Async implementation of the dev command."""
    
    try:
        app_path = Path(app_dir).resolve()
        
        if verbose:
            click.echo(f"🚀 Starting development mode for app in: {app_path}")
            click.echo(f"   Instance: {to_instance}")
        
        # Step 1: Load app configuration
        app_info = load_instance_app_info(app_path, to_instance)
        
        if not app_info or not app_info.get('app_id'):
            click.echo("❌ No app_id found in .fiber/{}/app.json".format(to_instance), err=True)
            click.echo("💡 Install the app first: fiber app install . --to-instance {}".format(to_instance))
            return
        
        app_id = app_info.get('app_id')
        version_id = app_info.get('last_version_id', 'latest')
        
        if verbose:
            click.echo(f"   📋 App ID: {app_id}")
            click.echo(f"   📋 Version ID: {version_id}")
        
        # Step 2: App info is already loaded from .fiber/{instance}/app.json
        
        # Step 3: Check if package.json exists
        package_json_path = app_path / 'package.json'
        if not package_json_path.exists():
            click.echo("❌ No package.json found in app directory", err=True)
            click.echo("💡 Make sure you're in a FiberWise app directory with npm setup")
            return
        
        # Step 4: Start npm dev process
        npm_process = _start_npm_dev(app_path, port, verbose)
        
        # Step 5: Start Python file watcher if enabled
        python_watcher = None
        if watch_python:
            if WATCHDOG_AVAILABLE:
                python_watcher = _start_python_watcher(app_path, verbose)
            else:
                click.echo("   ⚠️  Python file watching disabled: watchdog package not available")
                click.echo("      Install with: pip install watchdog")
                if verbose:
                    click.echo(f"      Import error: {WATCHDOG_IMPORT_ERROR}")
                    click.echo("      Or reinstall fiberwise: pip install -e . --force-reinstall")
        
        # Step 6: Keep running and handle cleanup
        try:
            click.echo("🎯 Development mode active! Press Ctrl+C to stop.")
            if verbose:
                click.echo("   📦 npm dev: Running")
                if watch_python:
                    click.echo("   🐍 Python watcher: Active")
                click.echo("   ⚡ Hot reload: Enabled")
            
            # Wait for user interrupt
            while True:
                await asyncio.sleep(1)
                
                # Check if npm process is still running
                if npm_process.poll() is not None:
                    click.echo("❌ npm dev process ended unexpectedly")
                    break
                    
        except KeyboardInterrupt:
            click.echo("\n🛑 Stopping development mode...")
            
        finally:
            # Cleanup
            if npm_process and npm_process.poll() is None:
                npm_process.terminate()
                try:
                    npm_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    npm_process.kill()
                if verbose:
                    click.echo("   ✅ npm dev process stopped")
            
            if python_watcher:
                python_watcher.stop()
                python_watcher.join()
                if verbose:
                    click.echo("   ✅ Python watcher stopped")
            
            click.echo("🎉 Development mode stopped")
        
    except Exception as e:
        click.echo(f"❌ Error in development mode: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)



def _start_npm_dev(app_path: Path, port: Optional[int], verbose: bool) -> subprocess.Popen:
    """Start the npm dev process."""
    npm_cmd = ['npm', 'run', 'dev']
    
    # Add port if specified
    if port:
        npm_cmd.extend(['--', '--port', str(port)])
    
    if verbose:
        click.echo(f"   🚀 Starting: {' '.join(npm_cmd)}")
    
    try:
        # Start npm dev process
        npm_process = subprocess.Popen(
            npm_cmd,
            cwd=app_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Start a thread to print npm output
        def print_npm_output():
            for line in iter(npm_process.stdout.readline, ''):
                if line.strip():
                    click.echo(f"   [npm] {line.strip()}")
        
        output_thread = threading.Thread(target=print_npm_output, daemon=True)
        output_thread.start()
        
        # Give npm a moment to start
        time.sleep(2)
        
        if npm_process.poll() is None:
            if verbose:
                click.echo("   ✅ npm dev started successfully")
        else:
            raise Exception(f"npm dev failed to start (exit code: {npm_process.poll()})")
        
        return npm_process
        
    except FileNotFoundError:
        raise Exception("npm not found. Please install Node.js and npm.")
    except Exception as e:
        raise Exception(f"Failed to start npm dev: {e}")


class PythonFileHandler(FileSystemEventHandler):
    """Handle Python file changes."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.last_event_time = {}
        self.debounce_seconds = 1.0  # Debounce rapid file changes
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        if not event.src_path.endswith('.py'):
            return
        
        # Debounce rapid changes
        now = time.time()
        if event.src_path in self.last_event_time:
            if now - self.last_event_time[event.src_path] < self.debounce_seconds:
                return
        
        self.last_event_time[event.src_path] = now
        
        rel_path = os.path.relpath(event.src_path)
        click.echo(f"   🐍 Python file changed: {rel_path}")
        
        if self.verbose:
            click.echo(f"      📝 You may need to restart any running functions/agents")


def _start_python_watcher(app_path: Path, verbose: bool) -> Optional[Observer]:
    """Start watching Python files for changes."""
    if not WATCHDOG_AVAILABLE:
        return None
        
    try:
        event_handler = PythonFileHandler(verbose)
        observer = Observer()
        
        # Watch functions directory
        functions_dir = app_path / 'functions'
        if functions_dir.exists():
            observer.schedule(event_handler, str(functions_dir), recursive=True)
            if verbose:
                click.echo(f"   👀 Watching: {functions_dir}")
        
        # Watch agents directory  
        agents_dir = app_path / 'agents'
        if agents_dir.exists():
            observer.schedule(event_handler, str(agents_dir), recursive=True)
            if verbose:
                click.echo(f"   👀 Watching: {agents_dir}")
        
        # Watch any other Python files in root
        observer.schedule(event_handler, str(app_path), recursive=False)
        
        observer.start()
        
        if verbose:
            click.echo("   ✅ Python file watcher started")
        
        return observer
        
    except Exception as e:
        if verbose:
            click.echo(f"   ⚠️  Warning: Could not start Python watcher: {e}")
        return None


@app.command()
@click.argument('app_path', type=click.Path(exists=True, path_type=Path), default='.')
@click.option('--to-instance', help='Target instance')
@click.option('--force', is_flag=True, help='Skip confirmation')
@click.option('--delete-data', is_flag=True, help='Delete data tables')
def delete(app_path: Path, to_instance: str, force: bool, delete_data: bool):
    """Delete app from FiberWise instance"""
    import requests
    
    try:
        # Initialize centralized context
        ctx = AppOperationContext(app_path, to_instance, None, False)
        
        # Check if app exists locally
        if not ctx.app_info or not ctx.get_app_id():
            click.echo("❌ No app found to delete. App must be installed first.", err=True)
            return
        
        app_id = ctx.get_app_id()
        app_name = "Unknown"
        
        if ctx.manifest_data:
            app_name = ctx.manifest_data.get('app', {}).get('name', 'Unknown')
        
        # Safety confirmation
        if not force:
            click.echo(f"⚠️  You are about to DELETE the app: {app_name}")
            click.echo(f"   Instance: {ctx.instance_name}")
            click.echo(f"   App ID: {app_id}")
            
            if delete_data:
                click.echo("   🗑️  This will PERMANENTLY DELETE all data tables!")
            else:
                click.echo("   📊 Data tables will be preserved")
                
            if not click.confirm("Are you sure you want to continue?"):
                click.echo("❌ Deletion cancelled")
                return
        
        # Get API configuration
        if not ctx.has_valid_api_config():
            click.echo("❌ Invalid API configuration", err=True)
            return
            
        api_endpoint, api_key = ctx.get_api_config()
        
        # Make delete request to complete deletion endpoint
        delete_url = f"{api_endpoint}/api/apps/{app_id}/complete"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        params = {
            "delete_data_tables": delete_data,
            "delete_bundles": True,
            "create_backup": False
        }
        
        click.echo(f"🗑️  Deleting app {app_name}...")
        
        response = requests.delete(delete_url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 204:
            click.echo("✅ App deleted successfully from server")
            
            # Clean up local app info file
            fiber_dir = app_path / FIBER_DATA_DIR
            instance_dir = fiber_dir / ctx.instance_name
            app_info_file = instance_dir / APP_INFO_FILE
            
            if app_info_file.exists():
                app_info_file.unlink()
                click.echo("✅ Local app info cleaned up")
            
            # Remove instance directory if empty
            if instance_dir.exists() and not any(instance_dir.iterdir()):
                instance_dir.rmdir()
                click.echo("✅ Instance directory cleaned up")
            
        elif response.status_code == 404:
            click.echo("⚠️  App not found on server, cleaning up local files", err=True)
            
            # Still clean up local files
            fiber_dir = app_path / FIBER_DATA_DIR
            instance_dir = fiber_dir / ctx.instance_name
            app_info_file = instance_dir / APP_INFO_FILE
            
            if app_info_file.exists():
                app_info_file.unlink()
                click.echo("✅ Local app info cleaned up")
                
        elif response.status_code == 403:
            click.echo("❌ Permission denied. You can only delete your own apps.", err=True)
            
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('detail', 'Unknown error')
            except:
                error_msg = f"HTTP {response.status_code}"
            
            click.echo(f"❌ Delete failed: {error_msg}", err=True)
    
    except requests.exceptions.RequestException as e:
        click.echo(f"❌ Network error: {e}", err=True)
    except Exception as e:
        click.echo(f"❌ Error deleting app: {e}", err=True)
