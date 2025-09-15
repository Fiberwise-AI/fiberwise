"""
Script to copy fiberwise-core-web to the web module directory during install or first run.
Excludes node_modules and other development files.
"""

import os
import shutil
from pathlib import Path

def copy_web_module(source_dir=None, target_dir=None):
    """
    Copy fiberwise-core-web to the web module directory, excluding development files.
    
    Args:
        source_dir: Source directory (defaults to ../../../fiberwise-core-web)
        target_dir: Target directory (defaults to ../web)
    """
    
    # Get current script directory
    script_dir = Path(__file__).parent
    
    # Set default paths
    if source_dir is None:
        source_dir = script_dir.parent.parent.parent / "fiberwise-core-web"
    else:
        source_dir = Path(source_dir)
        
    if target_dir is None:
        target_dir = script_dir.parent / "web"
    else:
        target_dir = Path(target_dir)
    
    # Files and directories to exclude
    exclude_patterns = {
        'node_modules',
        '.git',
        '.gitignore',
        '__pycache__',
        '*.pyc',
        '.pytest_cache',
        'dist',
        'build',
        '.vscode',
        '.idea',
        '*.log',
        'server.log',
        '*.duckdb',
        'fiberwise_dev.duckdb'
    }
    
    def should_exclude(path):
        """Check if a path should be excluded."""
        path_name = path.name
        
        # Check exact matches
        if path_name in exclude_patterns:
            return True
            
        # Check pattern matches
        for pattern in exclude_patterns:
            if '*' in pattern:
                if pattern.startswith('*') and path_name.endswith(pattern[1:]):
                    return True
                elif pattern.endswith('*') and path_name.startswith(pattern[:-1]):
                    return True
        
        return False
    
    def copy_directory(src, dst):
        """Recursively copy directory, excluding unwanted files."""
        if not dst.parent.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            
        if not dst.exists():
            dst.mkdir(exist_ok=True)
        
        for item in src.iterdir():
            if should_exclude(item):
                print(f"Excluding: {item}")
                continue
                
            src_item = src / item.name
            dst_item = dst / item.name
            
            if item.is_dir():
                copy_directory(src_item, dst_item)
            else:
                print(f"Copying: {src_item} -> {dst_item}")
                shutil.copy2(src_item, dst_item)
    
    # Validate source directory exists
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")
    
    print(f"Copying web module from {source_dir} to {target_dir}")
    
    # Remove target directory if it exists
    if target_dir.exists():
        print(f"Removing existing target directory: {target_dir}")
        def remove_readonly(func, path, _):
            """Remove readonly files on Windows."""
            os.chmod(path, 0o777)
            func(path)
        shutil.rmtree(target_dir, onerror=remove_readonly)
    
    # Copy the directory
    copy_directory(source_dir, target_dir)
    
    print(f"Web module copied successfully to {target_dir}")

if __name__ == "__main__":
    copy_web_module()