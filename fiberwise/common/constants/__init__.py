"""
Constants package for FiberWise common functionality.
Now imports from fiberwise_common for consistency.
"""

from fiberwise_common.constants import (
    CLI_APP_UUID,
    CLI_APP_SLUG,
    CLI_APP_NAME_TEMPLATE, 
    CLI_APP_DESCRIPTION_TEMPLATE,
    CLI_APP_VERSION,
    get_cli_app_name,
    get_cli_app_description,
    get_cli_user_email
)

__all__ = [
    'CLI_APP_UUID',
    'CLI_APP_SLUG',
    'CLI_APP_NAME_TEMPLATE',
    'CLI_APP_DESCRIPTION_TEMPLATE', 
    'CLI_APP_VERSION',
    'get_cli_app_name',
    'get_cli_app_description',
    'get_cli_user_email'
]
