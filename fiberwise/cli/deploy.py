import click
from pathlib import Path
from typing import Optional

from .core_commands import deploy as core_deploy


@click.group()
def deploy():
    """Deploy FiberWise applications and components for review."""
    pass


@deploy.command()
@click.argument('app_path', type=click.Path(exists=True, path_type=Path), default='.')
@click.option('--to-instance', help='Target FiberWise instance config name (uses default if not specified)')
@click.option('--verbose', is_flag=True, help='Enable verbose output')
@click.option('--no-build', is_flag=True, help='Skip build step and use existing bundle/dist')
@click.option('--no-version-increment', is_flag=True, help='Skip auto version increment')
@click.option('--version-increment', type=click.Choice(['major', 'minor', 'patch']), default='patch',
              help='Type of version increment (default: patch)')
def app(app_path: Path, to_instance: Optional[str], verbose: bool, no_build: bool, no_version_increment: bool, version_increment: str):
    """
    Deploy a FiberWise application for review.
    
    APP_PATH: Path to the application directory containing app_manifest.yaml/json (default: current directory)
    """
    # Use the centralized core_deploy command which already has proper context handling
    ctx = click.Context(core_deploy)
    ctx.params = {
        'app_path': app_path,
        'manifest': None,
        'config': None,
        'to_instance': to_instance,
        'verbose': verbose,
        'no_version_increment': no_version_increment,
        'version_increment': version_increment
    }
    
    # Call the core deploy command directly
    core_deploy.invoke(ctx)
