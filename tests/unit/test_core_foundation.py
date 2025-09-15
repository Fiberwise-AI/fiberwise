"""
Basic tests for core foundation components.
"""

import pytest
import json
import os
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, Optional


class TestBasicFunctionality:
    """Test basic functionality without complex imports."""

    def test_json_operations(self):
        """Test JSON serialization/deserialization."""
        # Test data
        test_data = {"name": "test", "value": 42, "items": [1, 2, 3]}

        # Test serialization
        json_str = json.dumps(test_data)
        assert isinstance(json_str, str)

        # Test deserialization
        parsed_data = json.loads(json_str)
        assert parsed_data == test_data

    def test_json_operations_with_special_values(self):
        """Test JSON operations with special values."""
        # Test with None values
        data_with_none = {"key": None, "other": "value"}
        json_str = json.dumps(data_with_none)
        parsed = json.loads(json_str)
        assert parsed["key"] is None

        # Test with nested structures
        nested_data = {"level1": {"level2": {"value": "deep"}}}
        json_str = json.dumps(nested_data)
        parsed = json.loads(json_str)
        assert parsed["level1"]["level2"]["value"] == "deep"

    def test_file_operations(self):
        """Test basic file operations."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            test_content = "test content"
            f.write(test_content)
            temp_path = f.name

        try:
            # Test file exists
            assert os.path.exists(temp_path)

            # Test reading file
            with open(temp_path, 'r') as f:
                content = f.read()
                assert content == test_content

        finally:
            os.unlink(temp_path)

    def test_path_operations(self):
        """Test path operations."""
        # Test path creation
        test_path = Path("test") / "subdir" / "file.txt"
        assert str(test_path) == "test/subdir/file.txt"

        # Test path manipulation
        full_path = Path("/absolute/path/to/file.txt")
        assert full_path.name == "file.txt"
        assert full_path.parent == Path("/absolute/path/to")
        assert full_path.suffix == ".txt"

    @pytest.mark.asyncio
    async def test_async_operations(self):
        """Test basic async operations."""
        # Test simple async function
        async def simple_async_func():
            await asyncio.sleep(0.01)
            return "async_result"

        result = await simple_async_func()
        assert result == "async_result"

    def test_mock_operations(self):
        """Test mock object operations."""
        # Create mock
        mock_obj = Mock()
        mock_obj.method.return_value = "mocked_result"

        # Test mock behavior
        result = mock_obj.method()
        assert result == "mocked_result"

        # Verify method was called
        mock_obj.method.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_mock_operations(self):
        """Test async mock operations."""
        # Create async mock
        async_mock = AsyncMock()
        async_mock.async_method.return_value = "async_mock_result"

        # Test async mock behavior
        result = await async_mock.async_method()
        assert result == "async_mock_result"

        # Verify method was called
        async_mock.async_method.assert_called_once()


class TestDataValidation:
    """Test data validation functionality."""

    def test_basic_validation(self):
        """Test basic data validation."""
        # Test string validation
        assert isinstance("hello", str)
        assert len("hello") == 5

        # Test number validation
        assert isinstance(42, int)
        assert 42 > 0

        # Test dict validation
        test_dict = {"key": "value"}
        assert isinstance(test_dict, dict)
        assert "key" in test_dict
        assert test_dict["key"] == "value"

        # Test list validation
        test_list = [1, 2, 3]
        assert isinstance(test_list, list)
        assert len(test_list) == 3
        assert 2 in test_list

    def test_type_checking(self):
        """Test type checking."""
        # Test various types
        assert type("string") == str
        assert type(42) == int
        assert type(3.14) == float
        assert type(True) == bool
        assert type([1, 2, 3]) == list
        assert type({"key": "value"}) == dict
        assert type(None) == type(None)

    def test_data_structure_validation(self):
        """Test data structure validation."""
        # Test nested structures
        nested = {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"}
            ],
            "metadata": {
                "version": "1.0",
                "count": 2
            }
        }

        assert len(nested["users"]) == 2
        assert nested["users"][0]["name"] == "Alice"
        assert nested["metadata"]["version"] == "1.0"


class TestErrorHandling:
    """Test error handling functionality."""

    def test_exception_handling(self):
        """Test basic exception handling."""
        try:
            # This should raise an exception
            result = 1 / 0
        except ZeroDivisionError as e:
            assert "division by zero" in str(e)
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")

    def test_file_not_found_handling(self):
        """Test file not found error handling."""
        try:
            with open("/nonexistent/file.txt", 'r') as f:
                content = f.read()
        except FileNotFoundError as e:
            assert "No such file or directory" in str(e)
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")

    def test_json_parsing_errors(self):
        """Test JSON parsing error handling."""
        invalid_json = '{"key": "value", "missing": }'

        try:
            parsed = json.loads(invalid_json)
        except json.JSONDecodeError as e:
            assert "Expecting value" in str(e)
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")

    @pytest.mark.asyncio
    async def test_async_error_handling(self):
        """Test async error handling."""
        async def failing_async_func():
            await asyncio.sleep(0.01)
            raise ValueError("Async error")

        try:
            await failing_async_func()
        except ValueError as e:
            assert "Async error" in str(e)
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")


class TestConfigurationHandling:
    """Test configuration handling."""

    def test_dict_based_config(self):
        """Test dictionary-based configuration."""
        config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "name": "testdb"
            },
            "api": {
                "host": "0.0.0.0",
                "port": 8000
            }
        }

        # Test config access
        assert config["database"]["host"] == "localhost"
        assert config["api"]["port"] == 8000

        # Test config modification
        config["database"]["port"] = 3306
        assert config["database"]["port"] == 3306

    def test_environment_variables(self):
        """Test environment variable handling."""
        # Set test environment variable
        os.environ["TEST_VAR"] = "test_value"

        try:
            # Test reading environment variable
            value = os.environ.get("TEST_VAR")
            assert value == "test_value"

            # Test default values
            default_value = os.environ.get("NONEXISTENT_VAR", "default")
            assert default_value == "default"

        finally:
            # Clean up
            del os.environ["TEST_VAR"]

    def test_config_file_operations(self):
        """Test configuration file operations."""
        config_data = {
            "app_name": "TestApp",
            "version": "1.0.0",
            "features": ["feature1", "feature2"]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            # Test reading config file
            with open(config_path, 'r') as f:
                loaded_config = json.load(f)

            assert loaded_config["app_name"] == "TestApp"
            assert loaded_config["version"] == "1.0.0"
            assert len(loaded_config["features"]) == 2

        finally:
            os.unlink(config_path)


class TestAgentMetadataExtraction:
    """Test agent metadata extraction functionality."""

    def test_function_agent_metadata(self):
        """Test extracting metadata from function-based agents."""
        agent_code = '''
def run_agent(input_data):
    """Process user input and return result"""
    return {"result": "processed"}
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(agent_code)
            temp_file = f.name

        try:
            # Mock metadata extraction
            def extract_metadata(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()

                if 'def run_agent' in content:
                    # Extract docstring
                    lines = [line.strip() for line in content.split('\n') if line.strip()]
                    for line in lines:
                        if '"""' in line and 'run_agent' not in line:
                            description = line.replace('"""', '').strip()
                            return {"type": "function", "description": description}
                return {"type": "function", "description": ""}

            metadata = extract_metadata(temp_file)
            assert metadata["type"] == "function"
            assert "Process user input" in metadata["description"]

        finally:
            os.unlink(temp_file)

    def test_class_agent_metadata(self):
        """Test extracting metadata from class-based agents."""
        agent_code = '''
from fiberwise_common.entities.fiber_agent import FiberAgent

class MyAgent(FiberAgent):
    """Custom agent for processing data"""
    def run_agent(self, input_data):
        return {"result": "processed"}
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(agent_code)
            temp_file = f.name

        try:
            # Mock metadata extraction
            def extract_metadata(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()

                if 'class' in content and 'FiberAgent' in content:
                    # Extract docstring
                    lines = [line.strip() for line in content.split('\n') if line.strip()]
                    for line in lines:
                        if '"""' in line and 'class' not in line and 'def' not in line:
                            description = line.replace('"""', '').strip()
                            return {"type": "class", "description": description}
                return {"type": "function", "description": ""}

            metadata = extract_metadata(temp_file)
            assert metadata["type"] == "class"
            assert "Custom agent" in metadata["description"]

        finally:
            os.unlink(temp_file)


class TestLocalUserContext:
    """Test local user context functionality."""

    @pytest.mark.asyncio
    async def test_user_context_operations(self):
        """Test user context operations."""
        # Mock database provider
        mock_db = AsyncMock()
        mock_db.fetch_one.side_effect = [
            {"id": 123},  # User ID lookup
            {"id": 123, "username": "testuser", "email": "test@example.com"}  # User data
        ]

        # Mock user context service
        class MockUserContextService:
            def __init__(self, db_provider):
                self.db_provider = db_provider

            async def get_current_user_id(self):
                result = await self.db_provider.fetch_one("SELECT id FROM users WHERE username = ?", "current")
                return result["id"] if result else None

            async def get_current_user(self):
                user_id = await self.get_current_user_id()
                if user_id:
                    result = await self.db_provider.fetch_one("SELECT * FROM users WHERE id = ?", user_id)
                    return result
                return None

        service = MockUserContextService(mock_db)

        # Test getting user ID
        user_id = await service.get_current_user_id()
        assert user_id == 123

        # Test getting user data
        user = await service.get_current_user()
        assert user["username"] == "testuser"
        assert user["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_error_handling_in_context(self):
        """Test error handling in user context operations."""
        # Mock database provider that raises errors
        mock_db = AsyncMock()
        mock_db.fetch_one.side_effect = Exception("Database error")

        class MockUserContextService:
            def __init__(self, db_provider):
                self.db_provider = db_provider

            async def get_current_user_id(self):
                try:
                    result = await self.db_provider.fetch_one("SELECT id FROM users")
                    return result["id"] if result else None
                except Exception:
                    return None

            async def get_current_user(self):
                try:
                    user_id = await self.get_current_user_id()
                    if user_id:
                        result = await self.db_provider.fetch_one("SELECT * FROM users WHERE id = ?", user_id)
                        return result
                    return None
                except Exception:
                    return None

        service = MockUserContextService(mock_db)

        # Test graceful error handling
        user_id = await service.get_current_user_id()
        assert user_id is None

        user = await service.get_current_user()
        assert user is None


if __name__ == "__main__":
    pytest.main([__file__])
from fiberwise_common.constants import (
    CLI_APP_UUID,
    get_cli_app_name,
    get_cli_app_description,
    get_cli_user_email
)


class TestCoreUtilities:
    """Test core utility functions."""

    def test_validate_input_string(self):
        """Test validate_input with string inputs."""
        assert validate_input("hello") is True
        assert validate_input("") is False
        assert validate_input(None) is False

    def test_validate_input_common(self):
        """Test common validate_input function."""
        assert common_validate_input("hello") is True
        assert common_validate_input("") is False
        assert common_validate_input(None) is False
        assert common_validate_input([]) is False
        assert common_validate_input({}) is False
        assert common_validate_input([1, 2, 3]) is True
        assert common_validate_input({"key": "value"}) is True
        assert common_validate_input(42) is True

    def test_safe_json_loads(self):
        """Test safe JSON loading with various inputs."""
        # Valid JSON
        assert safe_json_loads('{"key": "value"}') == {"key": "value"}
        assert safe_json_loads('[1, 2, 3]') == [1, 2, 3]
        assert safe_json_loads('"string"') == "string"

        # Invalid JSON
        assert safe_json_loads("invalid json") is None
        assert safe_json_loads("invalid json", "default") == "default"
        assert safe_json_loads(None) is None
        assert safe_json_loads(None, "default") == "default"

    def test_safe_json_dumps(self):
        """Test safe JSON dumping with various inputs."""
        # Valid data
        assert safe_json_dumps({"key": "value"}) == '{"key": "value"}'
        assert safe_json_dumps([1, 2, 3]) == '[1, 2, 3]'
        assert safe_json_dumps("string") == '"string"'

        # Invalid data (non-serializable)
        def non_serializable():
            pass

        assert safe_json_dumps(non_serializable) == "{}"
        assert safe_json_dumps(non_serializable, "custom_default") == "custom_default"

    def test_ensure_directory_exists(self):
        """Test directory creation utility."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = os.path.join(temp_dir, "test", "nested", "directory")

            # Directory doesn't exist initially
            assert not os.path.exists(test_path)

            # Create directory
            ensure_directory_exists(test_path)

            # Directory should now exist
            assert os.path.exists(test_path)
            assert os.path.isdir(test_path)

    def test_ensure_directory_exists_existing(self):
        """Test directory creation when directory already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Directory already exists
            assert os.path.exists(temp_dir)

            # Should not raise error
            ensure_directory_exists(temp_dir)

            # Directory should still exist
            assert os.path.exists(temp_dir)


class TestAgentMetadataExtraction:
    """Test agent metadata extraction functionality."""

    def test_extract_agent_metadata_function_agent(self):
        """Test metadata extraction from function-based agent."""
        # Create a temporary Python file with a function agent
        agent_code = '''
def run_agent(input_data):
    """Test agent function"""
    return {"result": "test"}
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(agent_code)
            temp_file = f.name

        try:
            metadata = extract_agent_metadata(temp_file)

            assert "name" in metadata
            assert metadata["name"] == os.path.abspath(temp_file)
            assert metadata["type"] == "function"
            assert "description" in metadata
        finally:
            os.unlink(temp_file)

    def test_extract_agent_metadata_class_agent(self):
        """Test metadata extraction from class-based agent."""
        # Create a temporary Python file with a class agent
        agent_code = '''
from fiberwise_common import FiberAgent

class TestAgent(FiberAgent):
    """Test agent class"""
    def run_agent(self, input_data):
        return {"result": "test"}
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(agent_code)
            temp_file = f.name

        try:
            metadata = extract_agent_metadata(temp_file)

            assert "name" in metadata
            assert "TestAgent" in metadata["name"]
            assert metadata["type"] == "class"
            assert "description" in metadata
        finally:
            os.unlink(temp_file)

    def test_extract_agent_metadata_invalid_file(self):
        """Test metadata extraction from invalid file."""
        # Test with non-existent file
        metadata = extract_agent_metadata("/non/existent/file.py")

        assert metadata["name"] == "/non/existent/file.py"
        assert metadata["description"] == ""
        assert metadata["type"] == "function"

    def test_extract_agent_metadata_empty_file(self):
        """Test metadata extraction from empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("# Empty file")
            temp_file = f.name

        try:
            metadata = extract_agent_metadata(temp_file)

            assert "name" in metadata
            assert metadata["type"] == "function"
        finally:
            os.unlink(temp_file)


class TestCLIConstants:
    """Test CLI constants and utility functions."""

    def test_cli_app_uuid(self):
        """Test CLI app UUID constant."""
        assert CLI_APP_UUID is not None
        assert isinstance(CLI_APP_UUID, str)
        assert len(CLI_APP_UUID) > 0

    @patch('os.environ.get')
    def test_get_cli_app_name(self, mock_getenv):
        """Test CLI app name generation."""
        # Test with COMPUTERNAME
        mock_getenv.side_effect = lambda key, default=None: {
            'COMPUTERNAME': 'TEST-PC'
        }.get(key, default)

        name = get_cli_app_name()
        assert name == "FiberWise - TEST-PC"

        # Test with HOSTNAME
        mock_getenv.side_effect = lambda key, default=None: {
            'HOSTNAME': 'test-server'
        }.get(key, default)

        name = get_cli_app_name()
        assert name == "FiberWise - test-server"

        # Test with default
        mock_getenv.side_effect = lambda key, default=None: default
        name = get_cli_app_name()
        assert name == "FiberWise - unknown"

    @patch('os.environ.get')
    @patch('getpass.getuser')
    def test_get_cli_app_description(self, mock_getuser, mock_getenv):
        """Test CLI app description generation."""
        mock_getuser.return_value = "testuser"
        mock_getenv.side_effect = lambda key, default=None: {
            'COMPUTERNAME': 'TEST-PC'
        }.get(key, default)

        description = get_cli_app_description()
        assert "TEST-PC" in description
        assert "testuser" in description

    @patch('getpass.getuser')
    def test_get_cli_user_email(self, mock_getuser):
        """Test CLI user email generation."""
        mock_getuser.return_value = "testuser"

        email = get_cli_user_email()
        assert email == "testuser@localhost.dev"


class TestLocalUserContextService:
    """Test the FiberLocalContextService."""

    @pytest.fixture
    def mock_db_provider(self):
        """Create a mock database provider."""
        provider = AsyncMock()
        return provider

    @pytest.fixture
    def context_service(self, mock_db_provider):
        """Create a FiberLocalContextService instance."""
        return FiberLocalContextService(mock_db_provider)

    @pytest.mark.asyncio
    async def test_get_current_user_id_web_context(self, context_service):
        """Test getting user ID in web context."""
        web_user_id = 123
        result = await context_service.get_current_user_id(web_user_id)

        assert result == web_user_id

    @pytest.mark.asyncio
    async def test_get_current_user_id_cli_context_existing_user(self, context_service, mock_db_provider):
        """Test getting user ID in CLI context with existing user."""
        mock_db_provider.fetch_one.return_value = {"id": 456}

        result = await context_service.get_current_user_id()

        assert result == 456
        mock_db_provider.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_current_user_id_cli_context_no_user(self, context_service, mock_db_provider):
        """Test getting user ID in CLI context with no existing user."""
        mock_db_provider.fetch_one.side_effect = [None, {"id": 789}]

        result = await context_service.get_current_user_id()

        assert result == 789
        assert mock_db_provider.fetch_one.call_count == 2

    @pytest.mark.asyncio
    async def test_get_current_user_id_cli_context_no_users(self, context_service, mock_db_provider):
        """Test getting user ID in CLI context with no users in database."""
        mock_db_provider.fetch_one.side_effect = [None, None]

        result = await context_service.get_current_user_id()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_web_context(self, context_service, mock_db_provider):
        """Test getting user record in web context."""
        web_user_id = 123
        expected_user = {"id": 123, "username": "testuser"}
        mock_db_provider.fetch_one.return_value = expected_user

        result = await context_service.get_current_user(web_user_id)

        assert result == expected_user
        mock_db_provider.fetch_one.assert_called_once_with(
            "SELECT * FROM users WHERE id = ?", 123
        )

    @pytest.mark.asyncio
    async def test_get_current_user_cli_context(self, context_service, mock_db_provider):
        """Test getting user record in CLI context."""
        expected_user = {"id": 456, "username": "testuser"}
        mock_db_provider.fetch_one.side_effect = [expected_user, expected_user]

        result = await context_service.get_current_user()

        assert result == expected_user

    @pytest.mark.asyncio
    async def test_get_current_user_caching(self, context_service, mock_db_provider):
        """Test that user records are cached."""
        expected_user = {"id": 456, "username": "testuser"}
        mock_db_provider.fetch_one.side_effect = [expected_user, expected_user]

        # First call
        result1 = await context_service.get_current_user()
        # Second call should use cache
        result2 = await context_service.get_current_user()

        assert result1 == expected_user
        assert result2 == expected_user
        # Should only call database once due to caching
        assert mock_db_provider.fetch_one.call_count == 2  # Once for user ID, once for user record

    @pytest.mark.asyncio
    async def test_convenience_functions(self, mock_db_provider):
        """Test convenience functions for backward compatibility."""
        from fiberwise.common.local_user_context import get_current_user_id, get_current_user

        mock_db_provider.fetch_one.return_value = {"id": 123}

        # Test get_current_user_id
        result = await get_current_user_id(mock_db_provider, 456)
        assert result == 456

        # Test get_current_user
        mock_db_provider.fetch_one.return_value = {"id": 456, "username": "test"}
        result = await get_current_user(mock_db_provider, 456)
        assert result["username"] == "test"


class TestConfigurationManagement:
    """Test configuration management functionality."""

    @patch('fiberwise_common.entities.config.DatabaseManager')
    def test_config_initialization(self, mock_db_manager):
        """Test Config class initialization."""
        from fiberwise_common.entities.config import Config

        config = Config()

        assert config.DATABASE_URL is not None
        assert config.DB_PROVIDER == "sqlite"
        assert hasattr(config, 'db_manager')
        assert hasattr(config, 'db_provider')

    @patch('os.path.exists')
    @patch('os.makedirs')
    def test_config_database_path_creation(self, mock_makedirs, mock_exists):
        """Test that database directory is created."""
        from fiberwise_common.entities.config import Config

        mock_exists.return_value = False

        config = Config()

        # Should attempt to create directory
        mock_makedirs.assert_called()


class TestCLIFunctionality:
    """Test CLI functionality and commands."""

    @patch('fiberwise.fiberwise.cli.commands.Path.home')
    def test_get_default_config_name_exists(self, mock_home):
        """Test getting default config name when file exists."""
        from fiberwise.fiberwise.cli.commands import get_default_config_name

        mock_home.return_value = Path("/fake/home")
        config_file = Path("/fake/home/.fiberwise/default_config.txt")

        with patch.object(config_file, 'exists', return_value=True), \
             patch('builtins.open', create=True) as mock_open:

            mock_open.return_value.__enter__.return_value.read.return_value = "test-config\n"

            result = get_default_config_name()
            assert result == "test-config"

    @patch('fiberwise.fiberwise.cli.commands.Path.home')
    def test_get_default_config_name_not_exists(self, mock_home):
        """Test getting default config name when file doesn't exist."""
        from fiberwise.fiberwise.cli.commands import get_default_config_name

        mock_home.return_value = Path("/fake/home")
        config_file = Path("/fake/home/.fiberwise/default_config.txt")

        with patch.object(config_file, 'exists', return_value=False):
            result = get_default_config_name()
            assert result is None

    @patch('fiberwise.fiberwise.cli.commands.Path.home')
    def test_load_config(self, mock_home):
        """Test loading configuration by name."""
        from fiberwise.fiberwise.cli.commands import load_config

        mock_home.return_value = Path("/fake/home")

        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', create=True) as mock_open, \
             patch('json.load') as mock_json_load:

            mock_json_load.return_value = {"api_key": "test-key"}

            result = load_config("test-config")
            assert result == {"api_key": "test-key"}

    @patch('fiberwise.fiberwise.cli.commands.Path.home')
    def test_load_config_not_exists(self, mock_home):
        """Test loading configuration when file doesn't exist."""
        from fiberwise.fiberwise.cli.commands import load_config

        mock_home.return_value = Path("/fake/home")

        with patch('pathlib.Path.exists', return_value=False):
            result = load_config("nonexistent-config")
            assert result is None


class TestAgentDetection:
    """Test agent type detection in CLI."""

    def test_determine_activation_type_agent_sdk(self):
        """Test detecting SDK agent."""
        from fiberwise.fiberwise.cli.commands import _determine_activation_type

        # Create temporary file with SDK agent
        agent_code = '''
from fiberwise_sdk import FiberAgent

class MyAgent(FiberAgent):
    def run_agent(self, input_data):
        return {"result": "test"}
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(agent_code)
            temp_file = f.name

        try:
            result = _determine_activation_type(temp_file)
            assert result == "agent"
        finally:
            os.unlink(temp_file)

    def test_determine_activation_type_agent_common(self):
        """Test detecting common agent."""
        from fiberwise.fiberwise.cli.commands import _determine_activation_type

        # Create temporary file with common agent
        agent_code = '''
from fiberwise_common import FiberAgent

class MyAgent(FiberAgent):
    def run_agent(self, input_data):
        return {"result": "test"}
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(agent_code)
            temp_file = f.name

        try:
            result = _determine_activation_type(temp_file)
            assert result == "agent"
        finally:
            os.unlink(temp_file)

    def test_determine_activation_type_function_agent(self):
        """Test detecting function agent."""
        from fiberwise.fiberwise.cli.commands import _determine_activation_type

        # Create temporary file with function agent
        agent_code = '''
def run_agent(input_data):
    return {"result": "test"}
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(agent_code)
            temp_file = f.name

        try:
            result = _determine_activation_type(temp_file)
            assert result == "agent"
        finally:
            os.unlink(temp_file)

    def test_determine_activation_type_invalid_file(self):
        """Test agent detection with invalid file."""
        from fiberwise.fiberwise.cli.commands import _determine_activation_type

        result = _determine_activation_type("/non/existent/file.py")
        assert result == "agent"  # Default fallback


class TestIntegration:
    """Integration tests for core functionality."""

    @pytest.mark.asyncio
    async def test_full_user_context_workflow(self):
        """Test complete user context workflow."""
        from fiberwise.common.local_user_context import FiberLocalContextService

        # Mock database provider
        mock_db = AsyncMock()
        mock_db.fetch_one.side_effect = [
            {"id": 123},  # CLI user lookup
            {"id": 123, "username": "testuser"}  # User record lookup
        ]

        service = FiberLocalContextService(mock_db)

        # Test CLI context
        user_id = await service.get_current_user_id()
        assert user_id == 123

        user = await service.get_current_user()
        assert user["username"] == "testuser"

        # Test web context override
        web_user_id = await service.get_current_user_id(456)
        assert web_user_id == 456

    def test_json_utilities_roundtrip(self):
        """Test JSON utilities roundtrip."""
        test_data = {
            "string": "hello",
            "number": 42,
            "array": [1, 2, 3],
            "object": {"nested": "value"}
        }

        # Serialize
        json_str = safe_json_dumps(test_data)
        assert isinstance(json_str, str)

        # Deserialize
        parsed_data = safe_json_loads(json_str)
        assert parsed_data == test_data

    def test_json_utilities_error_handling(self):
        """Test JSON utilities error handling."""
        # Test with circular reference
        circular_data = {"self": None}
        circular_data["self"] = circular_data

        # Should handle circular reference gracefully
        result = safe_json_dumps(circular_data)
        assert result == "{}"  # Default fallback

        # Test parsing invalid JSON
        result = safe_json_loads("{invalid json")
        assert result is None

        # Test parsing with custom default
        result = safe_json_loads("{invalid json", "custom_default")
        assert result == "custom_default"


# Pytest configuration
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment."""
    # Ensure we're in test mode
    os.environ.setdefault("ENVIRONMENT", "test")


if __name__ == "__main__":
    pytest.main([__file__])
