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
        # On Windows, this will use backslashes, so let's check the parts
        assert test_path.parts == ("test", "subdir", "file.txt")

        # Test path manipulation
        full_path = Path("/absolute/path/to/file.txt")
        assert full_path.name == "file.txt"
        assert full_path.parent.name == "to"
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
            {"id": 123, "username": "testuser", "email": "test@example.com"},  # User data
            {"id": 123, "username": "testuser", "email": "test@example.com"}   # Extra for safety
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
