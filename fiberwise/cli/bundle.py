from typing import Optional
import click
import sys
from pathlib import Path
from datetime import datetime

from fiberwise_common.utils.file_utils import load_manifest

# Define default manifest names (order matters for lookup)
DEFAULT_MANIFEST_FILENAMES = ["app_manifest.json", "app_manifest.yaml", "app_manifest.yml"]

def find_default_manifest(search_dir: Path) -> Optional[Path]:
    """Looks for default manifest files in the specified directory."""
    for filename in DEFAULT_MANIFEST_FILENAMES:
        path = search_dir / filename
        if path.is_file():
            click.echo(f"Found default manifest file: {path}", err=True)
            return path
    return None


@click.group()
def bundle():
    """Bundle management commands."""
    pass

@bundle.command()
@click.option(
    '--app-dir',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True),
    default='.', # Default to the current directory
    help='Path to the application directory containing the manifest.'
)
@click.option(
    '--env',
    type=click.Choice(['dev', 'prod', 'test'], case_sensitive=False),
    default='dev',
    show_default=True,
    help='Build environment (influences build commands like vite modes).'
)
@click.option(
    '--verbose',
    is_flag=True,
    default=False,
    help='Enable verbose output during the bundling process.'
)
def create(app_dir, env, verbose):
    """
    Bundles a Fiberwise application based on its manifest.

    This command finds the app manifest (app_manifest.yaml/json) in the APP_DIR,
    validates it, and prepares it for bundling.
    """
    app_path = Path(app_dir)

    # --- Find and Validate Manifest ---
    manifest_path = find_default_manifest(app_path)
    if manifest_path is None:
         click.echo(f"Error: Could not find a default manifest file ({', '.join(DEFAULT_MANIFEST_FILENAMES)}) in the app directory: {app_path}", err=True)
         click.echo("An app manifest is required for bundling.", err=True)
         sys.exit(1)

    click.echo(f"\nProcessing manifest file: {manifest_path}", err=True)
    
    try:
        # Load manifest
        manifest_data = load_manifest(manifest_path)
        app_name = manifest_data.get('app', {}).get('name', 'unknown')
        app_version = manifest_data.get('app', {}).get('version', '0.0.0')
        click.echo(f"Successfully loaded manifest for app: '{app_name}' v{app_version}", err=True)
    except Exception as e:
        click.echo(f"Error processing manifest file: {e}", err=True)
        sys.exit(1)

    # Calculate the standard output directory path for intermediate files
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    intermediate_output_path = app_path / ".fw-data" / "bundle_standalone" / timestamp

    click.echo(f"Starting bundle process for app in: {app_path}")
    click.echo(f"Intermediate output will be placed in: {intermediate_output_path}")
    click.echo(f"Environment: {env}")
    if verbose:
        click.echo("Verbose mode enabled.")

    try:
        # Create output directory
        intermediate_output_path.mkdir(parents=True, exist_ok=True)
        
        # Copy manifest to output directory
        import shutil
        output_manifest_path = intermediate_output_path / manifest_path.name
        shutil.copy2(manifest_path, output_manifest_path)
        
        click.echo(click.style(f"\n✅ Bundle preparation completed successfully!", fg='green'))
        click.echo(f"Manifest copied to: {output_manifest_path}")
        click.echo("Note: Full bundling service implementation is in progress.")

    except Exception as e:
        # Catch any unexpected errors during bundle process
        click.echo(click.style(f"\n❌ An unexpected error occurred during bundling: {e}", fg='red'), err=True)
        sys.exit(1)
