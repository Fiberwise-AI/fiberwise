"""
FiberWise common utilities - simplified flat structure.

This module re-exports from fiberwise_common for most functionality,
with a few local utilities specific to the CLI package.
"""

# Re-export from fiberwise_common for backward compatibility
from fiberwise_common import (
    DatabaseProvider, 
    SQLiteProvider, 
    DatabaseManager,
    Config,
    FiberAgent,
    FiberInjectable
)
from fiberwise_common.services import AgentService
from fiberwise_common.constants import (
    CLI_APP_UUID,
    get_cli_app_name,
    get_cli_app_description, 
    get_cli_user_email
)

# Local utilities
from .local_user_context import FiberLocalContextService, get_current_user_id, get_current_user
from .helpers import validate_input

__all__ = [
    # From fiberwise_common
    'DatabaseProvider',
    'SQLiteProvider', 
    'DatabaseManager',
    'Config',
    'FiberAgent',
    'FiberInjectable',
    'AgentService',
    'CLI_APP_UUID',
    'get_cli_app_name',
    'get_cli_app_description',
    'get_cli_user_email',
    
    # Local utilities
    'FiberLocalContextService',
    'get_current_user_id',
    'get_current_user',
    'validate_input'
]
