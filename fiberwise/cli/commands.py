import json
import click
import os
import asyncio
import uuid
import getpass
import traceback
from pathlib import Path
from fiberwise_common.services import AgentService
from fiberwise_common import DatabaseProvider

# Import FiberWise SDK for activation
try:
    from fiberwise_sdk import FiberApp, FiberWiseConfig
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
from fiberwise_common.entities.config import Config
from fiberwise_common.constants import CLI_APP_UUID, get_cli_app_name, get_cli_app_description, get_cli_user_email
from fiberwise_common.constants import (
    CLI_APP_UUID, 
    CLI_APP_SLUG,
    get_cli_app_name, 
    get_cli_app_description,
    get_cli_user_email,
    CLI_APP_VERSION
)

# Configuration loading for --to-instance support
FIBERWISE_DIR = Path.home() / ".fiberwise"
CONFIG_DIR = FIBERWISE_DIR / "configs"
DEFAULT_CONFIG_MARKER_FILE = FIBERWISE_DIR / "default_config.txt"

def get_default_config_name():
    """Get the name of the default configuration."""
    if DEFAULT_CONFIG_MARKER_FILE.exists():
        try:
            with open(DEFAULT_CONFIG_MARKER_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            pass
    return None

def load_config(config_name):
    """Load configuration by name."""
    if not config_name:
        return None
    
    # Sanitize config name for filename
    safe_filename = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in config_name)
    config_file = CONFIG_DIR / f"{safe_filename}.json"
    
    if not config_file.exists():
        return None
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def create_fiber_app_config(to_instance, verbose):
    """Create FiberApp configuration for server-based instances (not direct local)."""
    if to_instance == 'local':
        # This shouldn't be called for 'local' - that uses direct ActivationService
        raise ValueError("create_fiber_app_config should not be called for 'local' instance")
    else:
        if verbose:
            click.echo(f"🌐 Loading remote configuration for: {to_instance}")
        
        # Load remote configuration
        config_data = load_config(to_instance)
        if not config_data:
            # Try default config if specified instance not found
            default_config_name = get_default_config_name()
            if default_config_name:
                config_data = load_config(default_config_name)
                if verbose:
                    click.echo(f"Using default config: {default_config_name}")
        
        if not config_data:
            raise click.ClickException(
                f"Configuration '{to_instance}' not found. Use 'fiber account add-config' to create configurations."
            )
        
        # Extract required fields for SDK
        api_key = config_data.get('api_key') or config_data.get('fiberwise_api_key')
        base_url = config_data.get('base_url') or config_data.get('fiberwise_base_url')
        
        if not api_key or not base_url:
            raise click.ClickException(
                f"Invalid configuration '{to_instance}'. Missing api_key or base_url."
            )
        
        return {
            'api_key': api_key,
            'base_url': base_url,
            'use_local': False
        }

# Import for password hashing fallback
try:
    from passlib.context import CryptContext
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:
    _pwd_context = None

@click.group()
def cli():
    """Fiberwise command line interface"""
    pass

# Import web commands
from .start_enhanced import start
cli.add_command(start)

# Import setup command and its subcommands
from .initialize import setup, clean
cli.add_command(setup)
cli.add_command(clean)

# Import seed user commands
# from .seed_user import seed_user, seed_system_user
# cli.add_command(seed_user, name='seed-user')
# cli.add_command(seed_system_user, name='seed-system-user')

# Import account management commands
from .account import account
cli.add_command(account)

# Import app management commands
from .app import app
cli.add_command(app)

# Import bundle management commands
# from .bundle import bundle
# cli.add_command(bundle)

# Import install commands - this will be moved to app install
# from .install import install
# cli.add_command(install)

# Import function and pipeline commands
from .functions import functions
cli.add_command(functions)

# Import new activate command from core_commands
from .core_commands import activate
cli.add_command(activate)


def _determine_activation_type(file_path: str) -> str:
    """Determine activation type by analyzing file contents"""
    print(f"Determining activation type for file: {file_path}")

    if not file_path:
        return 'function'
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Check for Agent (SDK and common imports)
            agent_imports = [
                'from fiberwise_sdk import Agent',
                'from fiberwise_sdk import FiberAgent',
                'from fiberwise_common import FiberAgent',
                'from fiberwise_common.entities import FiberAgent'
            ]
            
            has_agent_import = any(import_stmt in content for import_stmt in agent_imports)
            has_agent_class = 'class ' in content and ('(Agent)' in content or '(FiberAgent)' in content)
            
            # Also check for run_agent function which is the common pattern
            has_run_agent = 'def run_agent(' in content
            
            if has_agent_import and has_agent_class:
                return 'agent'
            elif has_run_agent:
                # If it has run_agent function, treat it as an agent
                return 'agent'
            
    except (IOError, UnicodeDecodeError):
        pass
        
    # Default to agent if it has common agent patterns
    return 'agent'

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
        
        # Ensure user and app exist using provider directly
        user_ok, app_ok = await _ensure_default_user_and_app(config.db_provider, verbose)
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


async def _ensure_default_user_and_app(db_provider, verbose: bool = False) -> tuple[bool, bool]:
    """
    Simple CLI check to ensure at least 1 user and 1 app exist.
    Creates them if missing using the CLI constants.
    
    Returns:
        tuple[bool, bool]: (user_exists_or_created, app_exists_or_created)
    """
    import getpass
    import uuid
    
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
                CLI_APP_UUID, "fiberwise-cli", app_name, app_description, "1.0.0", user_id
            )
            
            if verbose:
                click.echo(f"[OK] Created app: {app_name} (ID: {CLI_APP_UUID})")
        else:
            if verbose:
                click.echo(f"[OK] App exists: {apps[0]['name']} (ID: {apps[0]['app_id']})")
        
        return True, True
        
    except Exception as e:
        click.echo(f"[ERROR] Error ensuring user/app: {e}", err=True)
        return False, False




@cli.command()
@click.option('--worker-type', '-w', default='local', 
              type=click.Choice(['local', 'celery', 'redis']),
              help='Type of worker to use')
@click.option('--worker-id', default=None,
              help='Worker ID (auto-generated if not provided)')
@click.option('--max-jobs', '-j', default=None, type=int,
              help='Maximum number of jobs to process before stopping')
@click.option('--timeout', '-t', default=None, type=int,
              help='Timeout in seconds for job processing')
@click.option('--verbose', '-v', is_flag=True, 
              help='Enable verbose output')
@click.option('--config-file', '-c', default=None,
              help='Path to worker configuration file')
def worker(worker_type, worker_id, max_jobs, timeout, verbose, config_file):
    """Start a worker to process agent activations"""
    import asyncio
    import signal
    import logging
    from fiberwise.common.services.sqlite_activation_processor import SQLiteActivationWorker
    from fiberwise.common.services.database import SQLiteProvider
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load configuration
    worker_config = {
        'worker_type': worker_type,
    }
    
    if worker_id:
        worker_config['worker_id'] = worker_id
    
    if config_file:
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                worker_config.update(file_config)
        except Exception as e:
            click.echo(f"Error loading config file: {e}", err=True)
            return
    
    # Create database provider
    db_provider = SQLiteProvider("./fiberwise.db")
    
    # Create worker
    worker = SQLiteActivationWorker(db_provider, worker_config)
    
    click.echo(f"Starting {worker_type} worker...")
    if worker_id:
        click.echo(f"Worker ID: {worker_id}")
    if max_jobs:
        click.echo(f"Max jobs: {max_jobs}")
    if timeout:
        click.echo(f"Timeout: {timeout}s")
    
    async def main():
        # Setup signal handlers
        def signal_handler():
            click.echo("\nShutting down worker...")
            asyncio.create_task(worker.stop())
        
        if hasattr(signal, 'SIGINT'):
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGINT, signal_handler)
        
        try:
            await worker.start()
            
            # If max_jobs is specified, monitor job count
            if max_jobs:
                jobs_processed = 0
                while jobs_processed < max_jobs and worker._running:
                    await asyncio.sleep(1)
                    # This would need to be implemented in the worker
                    # jobs_processed = worker.get_jobs_processed()
                
                click.echo(f"Processed {max_jobs} jobs, stopping worker...")
                await worker.stop()
            else:
                # Run indefinitely until stopped
                while worker._running:
                    await asyncio.sleep(1)
        
        except KeyboardInterrupt:
            click.echo("\nReceived interrupt signal, stopping...")
        except Exception as e:
            click.echo(f"Worker error: {e}", err=True)
        finally:
            await worker.stop()
    
    # Run the worker
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        click.echo("\nWorker stopped by user")
    except Exception as e:
        click.echo(f"Error running worker: {e}", err=True)


# @cli.command()
# @click.option('--worker-type', '-w', default='local',
#               type=click.Choice(['local', 'celery', 'redis']),
#               help='Type of worker to test')
# @click.option('--verbose', '-v', is_flag=True,
#               help='Enable verbose output')
# def test_worker(worker_type, verbose):
#     """Test worker functionality with a simple job"""
#     import asyncio
#     import logging
#     from fiberwise.common.services.sqlite_activation_processor import SQLiteActivationProcessor
#     from fiberwise.common.services.database import SQLiteProvider
#     
#     # Setup logging
#     logging.basicConfig(
#         level=logging.INFO if verbose else logging.WARNING,
#         format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
#     )
#     
#     click.echo(f"Testing {worker_type} worker...")
#     
#     async def test():
#         # Create database provider
#         db_provider = SQLiteProvider("./fiberwise.db")
#         
#         # Create processor
#         worker_config = {'worker_type': worker_type}
#         processor = SQLiteActivationProcessor(db_provider, worker_config)
#         
#         try:
#             await processor.start()
#             
#             # Create a test activation
#             test_activation = {
#                 'activation_id': 'test-123',
#                 'agent_id': 'test-agent',
#                 'input_data': {'message': 'Hello from test!'}
#             }
#             
#             click.echo("Submitting test job...")
#             job_id = await processor.process_activation(test_activation)
#             
#             click.echo(f"Job submitted with ID: {job_id}")
#             
#             # Wait for completion
#             click.echo("Waiting for job completion...")
#             result = await processor.wait_for_job_completion(job_id, timeout=30)
#             
#             click.echo(f"Job completed with status: {result.status}")
#             if result.output_data:
#                 click.echo(f"Output: {json.dumps(result.output_data, indent=2)}")
#             if result.error:
#                 click.echo(f"Error: {result.error}")
#                 
#         except Exception as e:
#             click.echo(f"Test failed: {e}", err=True)
#         finally:
#             await processor.stop()
#     
#     # Run the test
#     try:
#         asyncio.run(test())
#         click.echo("Worker test completed")
#     except Exception as e:
#         click.echo(f"Test error: {e}", err=True)

# Agent Management Commands (Internal only - not exposed to CLI)
# These are kept for potential future admin/debugging needs

def _get_agent_info_from_file(file_path, activation_service):
    """Internal function to get agent info from file path"""
    agent = activation_service.get_or_create_agent_from_file(file_path)
    return agent

# Internal function for potential admin use
def _run_agent_by_id(agent_id, input_data=None, version='latest', verbose=False):
    """Internal function to run agent by GUID - not exposed to CLI"""
    config = Config()
    
    parsed_input_data = None
    if input_data:
        try:
            parsed_input_data = json.loads(input_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON input data: {e}")
    
    from fiberwise_common.services.service_registry import ServiceRegistry
    activation_service = ServiceRegistry(config.db_provider)
    
    result = activation_service.activate(
        agent_id=agent_id,
        input_data=parsed_input_data,
        version=version,
        verbose=verbose
    )
    
    return result

# @cli.command()
# @click.option('--verbose', is_flag=True, help="Enable verbose output")
# def list_agents(verbose):
#     """List all registered agents"""
#     asyncio.run(_list_agents_async(verbose))
# 
# async def _list_agents_async(verbose):
#     """Async implementation for list_agents"""
#     config = Config()
#     
#     try:
#         # Initialize database first
#         if not await _run_common_migrations_and_setup(config, verbose):
#             click.echo("Failed to initialize database", err=True)
#             return
#         
#         activation_service = ActivationService(config.db_provider, config)
#         
#         agents = await activation_service.db_provider.fetch_all(
#             "SELECT * FROM agents ORDER BY created_at DESC"
#         )
#         
#         if not agents:
#             click.echo("No agents found")
#             return
#             
#         for agent in agents:
#             click.echo(f"{agent['agent_id']} - {agent['name']}")
#             if agent['description']:
#                 click.echo(f"  Description: {agent['description']}")
#             if verbose:
#                 click.echo(f"  Created: {agent['created_at']}")
#                 # Show version count
#                 version_count = await activation_service.db_provider.fetch_one(
#                     "SELECT COUNT(*) as count FROM agent_versions WHERE agent_id = ?",
#                     agent['agent_id']
#                 )
#                 count_value = version_count['count'] if version_count else 0
#                 click.echo(f"  Versions: {count_value}")
#             click.echo()
#             
#     except Exception as e:
#         click.echo(f"Error: {str(e)}", err=True)
