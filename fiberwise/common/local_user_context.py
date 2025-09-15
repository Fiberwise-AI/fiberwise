"""
FiberLocal context service for handling authentication in both CLI and web environments.

This module provides utilities for managing user context across different execution environments:
- CLI operations use the local system user (auto-created during migration)
- Web operations use the authenticated user from the session/token
"""

import os
import getpass
from typing import Optional, Dict, Any
from fiberwise_common.database.base import DatabaseProvider


class FiberLocalContextService:
    """
    Service for managing user context across CLI and web environments.
    
    This service provides a consistent interface for getting the current user
    regardless of whether the code is running in a CLI or web context.
    """
    
    def __init__(self, db_provider: DatabaseProvider):
        self.db_provider = db_provider
        self._current_user_id = None
        self._current_user = None
    
    async def get_current_user_id(self, web_user_id: Optional[int] = None) -> Optional[int]:
        """
        Get the current user ID based on context.
        
        Args:
            web_user_id: Optional user ID from web authentication middleware
            
        Returns:
            User ID for the current context, or None if no user found
        """
        # If web user ID is provided (from authentication middleware), use it
        if web_user_id is not None:
            return web_user_id
        
        # For CLI context, get or create local system user
        if self._current_user_id is None:
            self._current_user_id = await self._get_or_create_cli_user()
        
        return self._current_user_id
    
    async def get_current_user(self, web_user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get the current user record based on context.
        
        Args:
            web_user_id: Optional user ID from web authentication middleware
            
        Returns:
            User record dict, or None if no user found
        """
        user_id = await self.get_current_user_id(web_user_id)
        if not user_id:
            return None
        
        # Cache user record to avoid repeated queries
        if self._current_user is None or self._current_user.get('id') != user_id:
            self._current_user = await self.db_provider.fetch_one(
                "SELECT * FROM users WHERE id = ?", user_id
            )
        
        return self._current_user
    
    async def _get_or_create_cli_user(self) -> Optional[int]:
        """
        Get or create the CLI user for local machine operations.
        This ensures CLI operations are attributed to the current system user.
        """
        try:
            # Get current system user
            system_username = getpass.getuser()
            
            # Check if user exists
            user = await self.db_provider.fetch_one(
                "SELECT id FROM users WHERE username = ?", 
                system_username
            )
            
            if user:
                return user['id']
            
            # If user doesn't exist, they should have been created during migration
            # Let's try to find any user as fallback
            any_user = await self.db_provider.fetch_one("SELECT id FROM users LIMIT 1")
            if any_user:
                return any_user['id']
            
            return None
        except Exception as e:
            print(f"Warning: Could not determine CLI user: {e}")
            return None
    
    


# Convenience functions for backward compatibility
async def get_current_user_id(db_provider: DatabaseProvider, web_user_id: Optional[int] = None) -> Optional[int]:
    """Convenience function to get current user ID"""
    service = FiberLocalContextService(db_provider)
    return await service.get_current_user_id(web_user_id)


async def get_current_user(db_provider: DatabaseProvider, web_user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Convenience function to get current user record"""
    service = FiberLocalContextService(db_provider)
    return await service.get_current_user(web_user_id)
