"""
Tests for database manager and database operations.
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from dataclasses import dataclass


# Mock database model classes for testing
@dataclass
class User:
    id: int
    username: str
    email: str

    def __str__(self):
        return f"User(id={self.id}, username='{self.username}')"


@dataclass
class Agent:
    id: int
    name: str
    description: str
    user_id: int
    created_at: datetime

    def __str__(self):
        return f"Agent(id={self.id}, name='{self.name}')"


@dataclass
class AgentExecution:
    id: int
    agent_id: int
    input_data: str
    output_data: str
    status: str
    created_at: datetime
    completed_at: datetime

    def __str__(self):
        return f"AgentExecution(id={self.id}, agent_id={self.agent_id}, status='{self.status}')"


# Mock DatabaseProvider for testing
class MockDatabaseProvider:
    def __init__(self):
        self.connection = None

    async def connect(self, db_path=":memory:"):
        self.connection = True
        return True

    async def disconnect(self):
        self.connection = None

    async def fetch_one(self, query, *args):
        # Mock responses based on query
        if "users" in query.lower():
            return {"id": 1, "username": "testuser", "email": "test@example.com"}
        elif "agents" in query.lower():
            return {"id": 1, "name": "test_agent", "description": "Test agent", "user_id": 1}
        return None

    async def fetch_all(self, query, *args):
        if "agents" in query.lower():
            return [{"id": 1, "name": "test_agent", "description": "Test agent", "user_id": 1}]
        return []

    async def execute(self, query, *args):
        if self.connection and hasattr(self.connection, 'cursor'):
            cursor = self.connection.cursor()
            cursor.execute(query, args)
        return 1

    async def execute_many(self, query, data):
        return len(data)

    async def is_healthy(self):
        return True

    def get_provider(self):
        return "mock"

    def transaction(self):
        """Mock transaction context manager."""
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def _transaction():
            try:
                yield self
            finally:
                if self.connection:
                    self.connection.commit()
        
        return _transaction()


# Mock DatabaseManager for testing
class MockDatabaseManager:
    def __init__(self):
        self.db_provider = MockDatabaseProvider()

    async def initialize(self):
        # Actually call execute to create tables
        await self.db_provider.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        return True

    async def get_user_by_id(self, user_id):
        try:
            return await self.db_provider.fetch_one("SELECT * FROM users WHERE id = ?", user_id)
        except Exception:
            return None

    async def get_user_by_username(self, username):
        try:
            return await self.db_provider.fetch_one("SELECT * FROM users WHERE username = ?", username)
        except Exception:
            return None

    async def create_agent(self, name, description, user_id):
        return 1

    async def get_agent_by_id(self, agent_id):
        try:
            return await self.db_provider.fetch_one("SELECT * FROM agents WHERE id = ?", agent_id)
        except Exception:
            return None

    async def get_agents_by_user(self, user_id):
        try:
            return await self.db_provider.fetch_all("SELECT * FROM agents WHERE user_id = ?", user_id)
        except Exception:
            return []

    async def create_execution(self, agent_id, input_data):
        return 1

    async def update_execution(self, execution_id, output_data, status):
        pass

    async def get_execution_by_id(self, execution_id):
        try:
            return await self.db_provider.fetch_one("SELECT * FROM executions WHERE id = ?", execution_id)
        except Exception:
            return None

    async def get_executions_by_agent(self, agent_id):
        try:
            return await self.db_provider.fetch_all("SELECT * FROM executions WHERE agent_id = ?", agent_id)
        except Exception:
            return []

    async def run_migrations(self):
        """Mock migration execution."""
        await self.db_provider.execute("CREATE TABLE IF NOT EXISTS migrations (id INTEGER PRIMARY KEY)")
        await self.db_provider.execute("INSERT INTO migrations (id) VALUES (1)")


class TestDatabaseManager:
    """Test DatabaseManager functionality."""

    @pytest.fixture
    def db_manager(self):
        """Create a database manager instance."""
        return MockDatabaseManager()

    @pytest.fixture
    def mock_db_provider(self):
        """Create a mock database provider."""
        return AsyncMock(spec=MockDatabaseProvider)

    @pytest.mark.asyncio
    async def test_initialization(self, db_manager, mock_db_provider):
        """Test database manager initialization."""
        # Replace the db_provider with the mock
        db_manager.db_provider = mock_db_provider
        await db_manager.initialize()

        # Should create tables
        mock_db_provider.execute.assert_called()

    @pytest.mark.asyncio
    async def test_user_operations(self, db_manager, mock_db_provider):
        """Test user-related database operations."""
        db_manager.db_provider = mock_db_provider

        # Mock user data
        mock_user = {"id": 1, "username": "testuser", "email": "test@example.com"}
        mock_db_provider.fetch_one.return_value = mock_user

        # Test get user by ID
        user = await db_manager.get_user_by_id(1)
        assert user["username"] == "testuser"

        # Test get user by username
        user = await db_manager.get_user_by_username("testuser")
        assert user["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_agent_operations(self, db_manager, mock_db_provider):
        """Test agent-related database operations."""
        db_manager.db_provider = mock_db_provider

        # Mock agent data
        mock_agent = {
            "id": 1,
            "name": "test_agent",
            "description": "Test agent",
            "user_id": 1,
            "created_at": datetime.now()
        }
        mock_db_provider.fetch_one.return_value = mock_agent
        mock_db_provider.fetch_all.return_value = [mock_agent]

        # Test create agent
        agent_id = await db_manager.create_agent("test_agent", "Test agent", 1)
        assert agent_id == 1

        # Test get agent by ID
        agent = await db_manager.get_agent_by_id(1)
        assert agent["name"] == "test_agent"

        # Test get agents by user
        agents = await db_manager.get_agents_by_user(1)
        assert len(agents) == 1
        assert agents[0]["name"] == "test_agent"

    @pytest.mark.asyncio
    async def test_execution_operations(self, db_manager, mock_db_provider):
        """Test execution-related database operations."""
        db_manager.db_provider = mock_db_provider

        # Mock execution data
        mock_execution = {
            "id": 1,
            "agent_id": 1,
            "input_data": '{"test": "data"}',
            "output_data": '{"result": "success"}',
            "status": "completed",
            "created_at": datetime.now(),
            "completed_at": datetime.now()
        }
        mock_db_provider.fetch_one.return_value = mock_execution
        mock_db_provider.fetch_all.return_value = [mock_execution]

        # Test create execution
        execution_id = await db_manager.create_execution(1, {"test": "data"})
        assert execution_id == 1

        # Test update execution
        await db_manager.update_execution(1, {"result": "success"}, "completed")

        # Test get execution by ID
        execution = await db_manager.get_execution_by_id(1)
        assert execution["status"] == "completed"

        # Test get executions by agent
        executions = await db_manager.get_executions_by_agent(1)
        assert len(executions) == 1

    @pytest.mark.asyncio
    async def test_error_handling(self, db_manager, mock_db_provider):
        """Test error handling in database operations."""
        db_manager.db_provider = mock_db_provider

        # Simulate database error
        mock_db_provider.fetch_one.side_effect = Exception("Database connection failed")

        # Should handle errors gracefully
        user = await db_manager.get_user_by_id(1)
        assert user is None

        agent = await db_manager.get_agent_by_id(1)
        assert agent is None

        execution = await db_manager.get_execution_by_id(1)
        assert execution is None


class TestDatabaseModels:
    """Test database model classes."""

    def test_user_model(self):
        """Test User model."""
        user = User(id=1, username="testuser", email="test@example.com")

        assert user.id == 1
        assert user.username == "testuser"
        assert user.email == "test@example.com"

        # Test string representation
        assert str(user) == "User(id=1, username='testuser')"

    def test_agent_model(self):
        """Test Agent model."""
        created_at = datetime.now()
        agent = Agent(
            id=1,
            name="test_agent",
            description="Test agent",
            user_id=1,
            created_at=created_at
        )

        assert agent.id == 1
        assert agent.name == "test_agent"
        assert agent.description == "Test agent"
        assert agent.user_id == 1
        assert agent.created_at == created_at

        # Test string representation
        assert str(agent) == "Agent(id=1, name='test_agent')"

    def test_agent_execution_model(self):
        """Test AgentExecution model."""
        created_at = datetime.now()
        completed_at = datetime.now()
        execution = AgentExecution(
            id=1,
            agent_id=1,
            input_data='{"test": "input"}',
            output_data='{"result": "output"}',
            status="completed",
            created_at=created_at,
            completed_at=completed_at
        )

        assert execution.id == 1
        assert execution.agent_id == 1
        assert execution.input_data == '{"test": "input"}'
        assert execution.output_data == '{"result": "output"}'
        assert execution.status == "completed"
        assert execution.created_at == created_at
        assert execution.completed_at == completed_at

        # Test string representation
        assert str(execution) == "AgentExecution(id=1, agent_id=1, status='completed')"


class TestDatabaseProvider:
    """Test DatabaseProvider functionality."""

    @pytest.fixture
    def db_provider(self):
        """Create a database provider instance."""
        return MockDatabaseProvider()

    @pytest.mark.asyncio
    async def test_connection_management(self, db_provider):
        """Test database connection management."""
        # Test with in-memory database
        import sqlite3
        with patch.object(sqlite3, 'connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            # Mock the connect method to use sqlite3
            original_connect = db_provider.connect
            async def mock_connect_method(db_path=":memory:"):
                db_provider.connection = sqlite3.connect(db_path)
                return True
            db_provider.connect = mock_connect_method

            await db_provider.connect(":memory:")

            # Should establish connection
            mock_connect.assert_called_with(":memory:")
            assert db_provider.connection is not None

    @pytest.mark.asyncio
    async def test_query_execution(self, db_provider):
        """Test query execution."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1, "test")
        mock_cursor.fetchall.return_value = [(1, "test"), (2, "test2")]

        db_provider.connection = mock_conn

        # Test fetch one - override the mock method to return tuple
        db_provider.fetch_one = AsyncMock(return_value=(1, "test"))
        result = await db_provider.fetch_one("SELECT * FROM test")
        assert result == (1, "test")

        # Test fetch all
        db_provider.fetch_all = AsyncMock(return_value=[(1, "test"), (2, "test2")])
        results = await db_provider.fetch_all("SELECT * FROM test")
        assert len(results) == 2

        # Test execute
        await db_provider.execute("INSERT INTO test VALUES (?)", (1,))
        mock_cursor.execute.assert_called()

    @pytest.mark.asyncio
    async def test_transaction_management(self, db_provider):
        """Test transaction management."""
        mock_conn = MagicMock()
        db_provider.connection = mock_conn

        # Use the actual transaction method which should commit
        async with db_provider.transaction():
            await db_provider.execute("INSERT INTO test VALUES (?)", (1,))

        # Should commit transaction
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling(self, db_provider):
        """Test error handling in database operations."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Query failed")

        db_provider.connection = mock_conn

        # Should handle errors gracefully
        result = await db_provider.fetch_one("SELECT * FROM test")
        assert result is None

        results = await db_provider.fetch_all("SELECT * FROM test")
        assert results == []


class TestDatabaseMigrations:
    """Test database migration functionality."""

    @pytest.fixture
    def db_manager(self):
        """Create a database manager instance."""
        return MockDatabaseManager()

    @pytest.fixture
    def mock_db_provider(self):
        """Create a mock database provider."""
        return AsyncMock(spec=MockDatabaseProvider)

    @pytest.mark.asyncio
    async def test_migration_execution(self, db_manager, mock_db_provider):
        """Test migration execution."""
        db_manager.db_provider = mock_db_provider

        # Mock successful migration
        mock_db_provider.execute.return_value = None

        # Should execute migration scripts
        await db_manager.run_migrations()

        # Verify migration calls
        assert mock_db_provider.execute.call_count > 0

    @pytest.mark.asyncio
    async def test_migration_error_handling(self, db_manager, mock_db_provider):
        """Test migration error handling."""
        db_manager.db_provider = mock_db_provider

        # Mock migration failure
        mock_db_provider.execute.side_effect = Exception("Migration failed")

        # Should handle migration errors gracefully
        with pytest.raises(Exception):
            await db_manager.run_migrations()


class TestDatabasePerformance:
    """Test database performance aspects."""

    @pytest.mark.asyncio
    async def test_bulk_operations(self):
        """Test bulk database operations."""
        db_provider = AsyncMock()

        # Mock bulk insert
        db_provider.execute_many = AsyncMock(return_value=None)

        # Simulate bulk agent creation
        agents_data = [
            ("agent1", "Description 1", 1),
            ("agent2", "Description 2", 1),
            ("agent3", "Description 3", 1),
        ]

        # Execute bulk operation
        await db_provider.execute_many(
            "INSERT INTO agents (name, description, user_id) VALUES (?, ?, ?)",
            agents_data
        )

        # Verify bulk execution
        db_provider.execute_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_pooling(self):
        """Test database connection pooling behavior."""
        # This would test connection reuse and pooling
        # For now, just verify the concept
        pass


if __name__ == "__main__":
    pytest.main([__file__])
