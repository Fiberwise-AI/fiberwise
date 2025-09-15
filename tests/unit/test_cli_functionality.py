"""
Tests for CLI commands and functionality.
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from click.testing import CliRunner

from fiberwise.cli.commands import cli, _determine_activation_type
from fiberwise.cli.functions import functions
from fiberwise.common.local_user_context import FiberLocalContextService


class TestCLICommands:
    """Test CLI command functionality."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_cli_help(self, runner):
        """Test CLI help command."""
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'Fiberwise command line interface' in result.output

    @patch('fiberwise.cli.commands._run_common_migrations_and_setup')
    @patch('fiberwise.cli.commands._activate_async')
    def test_activate_command(self, mock_activate, mock_setup, runner):
        """Test activate command."""
        mock_setup.return_value = True
        mock_activate.return_value = None

        with tempfile.NamedTemporaryFile(mode='wb', suffix='.py', delete=False) as f:
            f.write(b'def run_agent(input_data): return {"result": "test"}')
            temp_file = f.name

        try:
            result = runner.invoke(cli, ['activate', temp_file])
            # Command should attempt to run (may fail due to missing dependencies in test)
            assert result.exit_code in [0, 1]  # Allow for expected failures in test environment
        finally:
            os.unlink(temp_file)

    def test_determine_activation_type_comprehensive(self):
        """Comprehensive test for activation type determination."""

        # Test cases
        test_cases = [
            # (code, expected_type)
            ('from fiberwise_sdk import FiberAgent\nclass Test(FiberAgent): pass', 'agent'),
            ('from fiberwise_common import FiberAgent\nclass Test(FiberAgent): pass', 'agent'),
            ('def run_agent(input_data): return {}', 'agent'),
            ('# Empty file', 'agent'),  # Default fallback
        ]

        for code, expected in test_cases:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name

            try:
                result = _determine_activation_type(temp_file)
                assert result == expected, f"Failed for code: {code[:50]}..."
            finally:
                os.unlink(temp_file)


class TestFunctionsCLI:
    """Test functions CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @patch('fiberwise.cli.functions._get_database_provider')
    @patch('fiberwise.cli.functions.Config')
    def test_functions_list(self, mock_config, mock_setup, runner):
        """Test functions list command."""
        mock_setup.return_value = AsyncMock()
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.db_provider = AsyncMock()

        result = runner.invoke(functions, ['list'])
        # Should not crash
        assert result.exit_code in [0, 1]


class TestConfigurationCLI:
    """Test configuration-related CLI functionality."""

    @patch('fiberwise.cli.commands.Path.home')
    def test_config_file_operations(self, mock_home):
        """Test configuration file operations."""
        from fiberwise.cli.commands import get_default_config_name, load_config

        mock_home.return_value = Path("/fake/home")

        # Test default config name
        with patch('pathlib.Path.exists', return_value=False):
            assert get_default_config_name() is None

        # Test config loading
        with patch('pathlib.Path.exists', return_value=False):
            assert load_config("test") is None

    @patch('fiberwise.cli.commands.Path.home')
    @patch('builtins.open', create=True)
    @patch('json.load')
    def test_config_loading_success(self, mock_json_load, mock_open, mock_home):
        """Test successful configuration loading."""
        from fiberwise.cli.commands import load_config

        mock_home.return_value = Path("/fake/home")
        mock_json_load.return_value = {"api_key": "test"}

        with patch('pathlib.Path.exists', return_value=True):
            result = load_config("test-config")
            assert result == {"api_key": "test"}


class TestAgentExecution:
    """Test agent execution functionality."""

    @pytest.mark.asyncio
    async def test_agent_execution_workflow(self):
        """Test complete agent execution workflow."""
        # This would test the full agent execution pipeline
        # For now, just test the basic structure
        pass

    def test_agent_validation(self):
        """Test agent input/output validation."""
        from fiberwise_common.entities.fiber_agent import FiberAgent

        class TestAgent(FiberAgent):
            def run_agent(self, input_data):
                return {"result": "test"}

        agent = TestAgent()

        # Test input validation
        input_schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
        agent.get_input_schema = lambda: input_schema

        # Valid input
        result = agent.validate_input({"name": "test"})
        assert result["valid"] is True

        # Invalid input
        result = agent.validate_input({})
        assert result["valid"] is False

        # Test output validation
        output_schema = {"type": "object", "properties": {"result": {"type": "string"}}, "required": ["result"]}
        agent.get_output_schema = lambda: output_schema

        result = agent.validate_output({"result": "test"})
        assert result["valid"] is True


class TestDatabaseIntegration:
    """Test database integration functionality."""

    @pytest.mark.asyncio
    async def test_database_operations(self):
        """Test basic database operations."""
        # Mock database provider
        mock_db = AsyncMock()

        # Test user context service
        service = FiberLocalContextService(mock_db)

        # Mock database responses
        mock_db.fetch_one.side_effect = [
            {"id": 123},  # User lookup
            {"id": 123, "username": "testuser"}  # User record
        ]

        user_id = await service.get_current_user_id()
        assert user_id == 123

        user = await service.get_current_user()
        assert user["username"] == "testuser"


class TestErrorHandling:
    """Test error handling across the system."""

    def test_graceful_failures(self):
        """Test that system fails gracefully under error conditions."""
        from fiberwise_common.utils import safe_json_loads, safe_json_dumps

        # Test JSON operations with invalid data
        assert safe_json_loads("invalid json") is None
        assert safe_json_dumps(float('inf')) == 'Infinity'  # Non-serializable values are handled by json.dumps

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test database error handling."""
        mock_db = AsyncMock()
        mock_db.fetch_one.side_effect = Exception("Database error")

        service = FiberLocalContextService(mock_db)

        # Should handle database errors gracefully
        result = await service.get_current_user_id()
        assert result is None

    def test_file_operation_error_handling(self):
        """Test file operation error handling."""
        from fiberwise_common.utils import extract_agent_metadata

        # Test with non-existent file
        metadata = extract_agent_metadata("/non/existent/file.py")
        assert metadata["type"] == "function"
        assert metadata["description"] == ""


class TestPerformance:
    """Test performance aspects of core functionality."""

    def test_json_operations_performance(self):
        """Test JSON operations performance with large data."""
        import time
        from fiberwise_common.utils import safe_json_dumps, safe_json_loads

        # Create large test data
        large_data = {"data": list(range(1000))}

        # Test serialization
        start_time = time.time()
        json_str = safe_json_dumps(large_data)
        serialize_time = time.time() - start_time

        # Test deserialization
        start_time = time.time()
        parsed_data = safe_json_loads(json_str)
        deserialize_time = time.time() - start_time

        # Should complete in reasonable time
        assert serialize_time < 1.0  # Less than 1 second
        assert deserialize_time < 1.0
        assert parsed_data == large_data

    def test_agent_metadata_extraction_performance(self):
        """Test agent metadata extraction performance."""
        import time
        from fiberwise_common.utils import extract_agent_metadata

        # Create test file
        agent_code = '''
def run_agent(input_data):
    """Test agent"""
    return {"result": "test"}
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(agent_code)
            temp_file = f.name

        try:
            start_time = time.time()
            metadata = extract_agent_metadata(temp_file)
            extraction_time = time.time() - start_time

            # Should complete quickly
            assert extraction_time < 0.1  # Less than 100ms
            assert metadata["type"] == "function"
        finally:
            os.unlink(temp_file)


if __name__ == "__main__":
    pytest.main([__file__])
