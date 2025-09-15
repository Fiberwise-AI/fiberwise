"""
Core app management commands for FiberWise CLI.
"""
import click
import json
import time
import asyncio
import uuid
import ast
from pathlib import Path
from typing import Optional, Tuple, Literal
from datetime import datetime

from .app_context import AppOperationContext
from .app_utils import (
    update_manifest_version, 
    save_instance_app_info,
    load_instance_app_info,
    verify_deployed_files,
)
from .oauth_commands import register_oauth_authenticators_from_manifest


def display_operation_result(result, operation_name: str):
    """Display the results of an app operation in a user-friendly format."""
    if result.success:
        click.echo(f"[SUCCESS] {result.message}")
        
        for info in result.info_messages:
            click.echo(f"   [INFO] {info}")
        
        for warning in result.warnings:
            click.echo(f"   [WARNING] {warning}")
            
    else:
        click.echo(f"[ERROR] {operation_name} failed: {result.message}")
        
        if result.data.get("suggestion") == "update":
            click.echo("   [SUGGESTION] Use 'fiber app update .' to update the existing app")


def save_app_operation_info(ctx: AppOperationContext, app_path: Path, operation: str, result, verbose: bool):
    """Save app operation info after successful install/update."""
    if not result.success:
        return
    
    if verbose:
        click.echo("💾 Updating local app operation info...")
    
    try:
        # Save operation info to instance-specific location only
        instance_app_info = load_instance_app_info(app_path, ctx.instance_name)
        
        app_info_updates = {
            'last_operation': operation,
            'last_operation_timestamp': datetime.now().isoformat(),
            'installation_instance' if operation == 'install' else 'last_instance_used': ctx.instance_name or "default"
        }
        instance_app_info.update(app_info_updates)
        
        if result.data and result.data.get("install_response"):
            install_response = result.data["install_response"]
            
            app_results = install_response.get("app", [])
            if app_results:
                app_result = app_results[0]
                app_id = app_result.get("component_id") or app_result.get("app_id")
                if app_id:
                    instance_app_info["app_id"] = app_id
                    if verbose:
                        click.echo(f"   📋 App ID: {app_id}")
            
            app_version_id = result.data.get("app_version_id")
            if app_version_id:
                instance_app_info["app_version_id"] = app_version_id
                if verbose:
                    click.echo(f"   📋 Version ID: {app_version_id}")
        
        if result.data and result.data.get("app_version_id"):
            app_version_id = result.data["app_version_id"]
            instance_app_info["app_version_id"] = app_version_id
            if verbose:
                click.echo(f"   📋 Version ID: {app_version_id}")
        
        if ctx.manifest_path:
            instance_app_info["last_manifest_version"] = ctx.manifest_data.get("app", {}).get("version") or ctx.manifest_data.get("app_version", "1.0.0")
            instance_app_info["manifest_path"] = str(ctx.manifest_path.resolve())
        
        instance_app_info["current_app_dir"] = str(app_path.resolve())
        instance_app_info["instance_name"] = ctx.instance_name
        
        save_instance_app_info(app_path, ctx.instance_name, instance_app_info)
        if verbose:
            click.echo(f"   💾 Saved to .fiber/{ctx.instance_name}/app.json")
                    
    except Exception as e:
        if verbose:
            click.echo(f"⚠️  Warning: Could not update app info: {e}")




@click.command()
@click.argument('app_path', type=click.Path(exists=True, path_type=Path), default='.')
@click.option('--manifest', '-m', type=click.Path(exists=True, path_type=Path), 
              help='Path to the app manifest file (JSON or YAML)')
@click.option('--config', '-c', help='Configuration profile to use')
@click.option('--to-instance', help='Target specific config instance by name')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.option('--no-version-increment', is_flag=True, help='Skip auto version increment')
@click.option('--version-increment', type=click.Choice(['major', 'minor', 'patch']), default='patch',
              help='Type of version increment (default: patch)')
def deploy(app_path: Path, manifest: Optional[Path], config: Optional[str], to_instance: Optional[str], 
            verbose: bool, no_version_increment: bool, version_increment: str):
    """Deploy an application for review (unpublished state)."""
    try:
        ctx = AppOperationContext(app_path, to_instance, config, verbose)
        
        if verbose:
            click.echo(f"Deploying app from: {app_path}")
            if manifest:
                click.echo(f"Using manifest: {manifest}")
        
        if not no_version_increment:
            if verbose:
                click.echo(f"🔢 Auto-incrementing version ({version_increment})...")
            
            new_version = update_manifest_version(app_path, version_increment, verbose)
            if new_version and verbose:
                click.echo(f"   Updated to version: {new_version}")
        
        app_manager = ctx.get_app_manager()
        result = app_manager.install_app(app_path, manifest)
        display_operation_result(result, "Deployment")
        
        if result.success:
            try:
                oauth_registered = register_oauth_authenticators_from_manifest(app_path, ctx.instance_name, verbose)
                if oauth_registered > 0:
                    click.echo(f"✅ Registered {oauth_registered} OAuth authenticator(s)")
            except Exception as e:
                if verbose:
                    click.echo(f"⚠️  Warning: Could not register OAuth authenticators: {e}")
        
        save_app_operation_info(ctx, app_path, 'deploy', result, verbose)
    
    except click.ClickException:
        return


def _detect_file_type(file_path: Path) -> Tuple[Optional[Literal['agent', 'pipeline']], Optional[str]]:
    """Detect if a file is an agent or a pipeline using AST parsing."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source)
        
        for node in ast.walk(tree):
            # Check for FiberAgent subclass
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == 'FiberAgent':
                        return 'agent', node.name
            # Check for execute function (pipeline)
            if isinstance(node, ast.FunctionDef) and node.name == 'execute':
                return 'pipeline', None
        
        return None, None
    except Exception:
        return None, None


async def _watch_execution(local_service, execution_type: str, execution_id: str):
    """Poll and display execution status."""
    click.echo(f"Watching execution {execution_id}...")
    
    if execution_type == "pipeline":
        table_name = "pipeline_executions"
        id_column = "execution_id"
        output_column = "results"
    else:
        table_name = "agent_activations"
        id_column = "activation_id"
        output_column = "output_data"
    
    while True:
        query = f"SELECT status, error, {output_column} FROM {table_name} WHERE {id_column} = ?"
        result = await local_service.db_provider.fetch_one(query, execution_id)
        
        if not result:
            click.echo("Execution record not found.")
            break
        
        status = result.get('status')
        click.echo(f"  Status: {status}")
        
        if status in ['completed', 'failed']:
            if status == 'failed':
                click.echo(f"  Error: {result.get('error')}")
            else:
                output = result.get(output_column)
                click.echo("  Output:")
                click.echo(json.dumps(output, indent=2))
            break
        
        time.sleep(2)


async def _activate_async(file_path: Path, input_data_dict: dict, watch: bool, ctx: AppOperationContext):
    """Async helper for the activate command."""
    local_service = ctx.get_local_service()
    
    entity_type, _ = _detect_file_type(file_path)
    
    if not entity_type:
        raise click.ClickException(f"Could not determine type (agent or pipeline) for file: {file_path}")
    
    click.echo(f"Activating {entity_type} from {file_path}...")
    
    # Use a relative path from the app root to find the entity in the DB
    try:
        relative_path = file_path.relative_to(ctx.app_path)
    except ValueError:
        relative_path = file_path

    if entity_type == 'pipeline':
        pipeline = await local_service.get_pipeline_by_filepath(str(relative_path))
        if not pipeline:
            raise click.ClickException(f"No pipeline found with file path: {relative_path}")
        
        pipeline_id = pipeline['pipeline_id']
        click.echo(f"Found pipeline: {pipeline['name']} (ID: {pipeline_id})")
        
        execution_data = {
            'pipeline_id': pipeline_id,
            'input_data': input_data_dict,
            'status': 'queued',
            'created_by': ctx.user_id,
        }
        execution = await local_service.create_pipeline_execution(execution_data)
        execution_id = execution['execution_id']
        click.echo(f"Created pipeline execution: {execution_id}")
        
        if watch:
            await _watch_execution(local_service, 'pipeline', execution_id)

    elif entity_type == 'agent':
        agent = await local_service.get_agent_by_filepath(str(relative_path))
        if not agent:
            raise click.ClickException(f"No agent found with file path: {relative_path}")
            
        agent_id = agent['agent_id']
        click.echo(f"Found agent: {agent['name']} (ID: {agent_id})")
        
        activation_data = {
            'agent_id': agent_id,
            'input_data': input_data_dict,
            'status': 'queued',
            'created_by': ctx.user_id,
        }
        activation = await local_service.create_agent_activation(activation_data)
        activation_id = activation['activation_id']
        click.echo(f"Created agent activation: {activation_id}")
        
        if watch:
            await _watch_execution(local_service, 'agent', activation_id)


@click.command()
@click.argument('file_path', type=click.Path(exists=True, path_type=Path))
@click.option('--input-data', '-d', help='Input data as a JSON string')
@click.option('--input-file', '-f', type=click.Path(exists=True, path_type=Path), help='Path to a JSON file with input data')
@click.option('--watch', '-w', is_flag=True, help='Watch for execution status updates')
@click.option('--config', '-c', help='Configuration profile to use')
@click.option('--to-instance', help='Target specific config instance by name')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
def activate(file_path: Path, input_data: Optional[str], input_file: Optional[Path], watch: bool,
             config: Optional[str], to_instance: Optional[str], verbose: bool):
    """Activate an agent or pipeline from a local file."""
    try:
        ctx = AppOperationContext(Path('.'), to_instance, config, verbose)
        
        input_data_dict = {}
        if input_file:
            with open(input_file, 'r') as f:
                input_data_dict = json.load(f)
        elif input_data:
            input_data_dict = json.loads(input_data)
            
        asyncio.run(_activate_async(file_path, input_data_dict, watch, ctx))

    except json.JSONDecodeError:
        raise click.ClickException("Invalid JSON in input data.")
    except Exception as e:
        raise click.ClickException(str(e))


@click.command()
@click.argument('app_path', type=click.Path(exists=True, path_type=Path), default='.')
@click.option('--manifest', '-m', type=click.Path(exists=True, path_type=Path), 
              help='Path to the app manifest file (JSON or YAML)')
@click.option('--config', '-c', help='Configuration profile to use')
@click.option('--to-instance', help='Target specific config instance by name')
@click.option('--force', '-f', is_flag=True, help='Force update even if no changes detected')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.option('--no-version-increment', is_flag=True, help='Skip auto version increment')
@click.option('--version-increment', type=click.Choice(['major', 'minor', 'patch']), default='patch',
              help='Type of version increment (default: patch)')
@click.option('--verify', is_flag=True, help='Verify deployed files after update')
def update(app_path: Path, manifest: Optional[Path], config: Optional[str], to_instance: Optional[str], 
           force: bool, verbose: bool, no_version_increment: bool, version_increment: str, verify: bool):
    """Update an installed application."""
    try:
        ctx = AppOperationContext(app_path, to_instance, config, verbose)
        
        if verbose:
            click.echo(f"Updating app at: {app_path}")
            if manifest:
                click.echo(f"Using manifest: {manifest}")
            if force:
                click.echo("Force update enabled")
        
        if not no_version_increment:
            if verbose:
                click.echo(f"🔢 Auto-incrementing version ({version_increment})...")
            
            new_version = update_manifest_version(app_path, version_increment, verbose)
            if new_version and verbose:
                click.echo(f"   Updated to version: {new_version}")
        
        app_manager = ctx.get_app_manager()
        result = app_manager.update_app(app_path, manifest, force)
        display_operation_result(result, "Update")
        
        if result.success:
            try:
                oauth_registered = register_oauth_authenticators_from_manifest(app_path, ctx.instance_name, verbose)
                if oauth_registered > 0:
                    click.echo(f"✅ Registered {oauth_registered} OAuth authenticator(s)")
            except Exception as e:
                if verbose:
                    click.echo(f"⚠️  Warning: Could not register OAuth authenticators: {e}")
            
            # Verify deployed files if requested
            if verify:
                click.echo("Running file verification...")
                try:
                    verify_deployed_files(app_path, ctx, result, verbose)
                except Exception as e:
                    click.echo(f"[WARNING] File verification failed: {e}")
                    if verbose:
                        import traceback
                        click.echo(traceback.format_exc())
        
        save_app_operation_info(ctx, app_path, 'update', result, verbose)
    
    except click.ClickException:
        return
