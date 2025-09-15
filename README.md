# FiberWise

A comprehensive command line tool and activation system for FiberWise agents with dependency injection support.

## Overview

FiberWise provides:
- **Agent Activation System**: Register, version, and execute agents
- **Dependency Injection**: Automatic service injection into agents
- **SDK Integration**: Seamless integration with `fiberwise_sdk`
- **Multi-Database Support**: SQLite, DuckDB, MySQL, PostgreSQL
- **CLI Interface**: Easy command-line activation and management
- **Web Interface**: Built-in web server for agent management

## Installation

```bash
pip install -e .
```

For the full SDK experience, also install:
```bash
pip install fiberwise-sdk
```

## Default Credentials

**First time setup:**
- Username: `admin`
- Email: `admin@fiberwise.local`
- Password: `fiber2025!`

See [DEFAULT_CREDENTIALS.md](../DEFAULT_CREDENTIALS.md) for complete details.

## Quick Start


### 1. Initialize the FiberWise Environment

```bash
# Initialize FiberWise project (creates config, database, and default admin user)
fiber initialize
```

**Options:**

- `--db-path <path>`: Set custom database file path (default: ./fiberwise.db)
- `--force`: Overwrite existing config/database if present
- `--no-admin`: Skip creation of default admin user
- `--no-web`: Do not launch the web UI after initialization
- `--no-browser`: Do not open browser after starting web UI
- `--host <host>`: Set web server host (default: 127.0.0.1)
- `--port <port>`: Set web server port (default: 8000)

Example:
```bash
fiber initialize --db-path ./mydb.db --no-browser --host 0.0.0.0 --port 3000
```

For details on how instance routing works with initialization and activation, see the [CLI Instance Routing Guide](../CLI_INSTANCE_ROUTING_GUIDE.md).

---

### 2. Start the Web Server

```bash
# Start FiberWise web interface (if not started by initialize)
fiber start
```

### 2. Configure Account and Providers

```bash
# Add your FiberWise API configuration
python -m fiberwise.cli account add-config --name "prod" --api-key "your-api-key" --base-url "https://api.fiberwise.ai" --set-default

# Import providers from your app for dependency injection
python -m fiberwise.cli account import-providers --default

# List available providers
python -m fiberwise.cli account list-providers
```

### 3. Create an Agent with Dependency Injection

```python
def run_agent(input_data, fiber=None, llm_service=None, storage=None, oauth_service=None):
    """Agent with automatic dependency injection"""
    result = {"input": input_data, "services": {}}
    
    # FiberApp SDK automatically injected
    if fiber:
        try:
            agents = await fiber.agents.list()
            result["services"]["fiber"] = f"Connected to FiberApp - {len(agents)} agents available"
        except Exception as e:
            result["services"]["fiber"] = f"FiberApp error: {e}"
    
    # LLM service automatically injected
    if llm_service:
        try:
            response = await llm_service.generate("Test prompt")
            result["services"]["llm"] = "LLM service connected"
        except Exception as e:
            result["services"]["llm"] = f"LLM error: {e}"
    
    # Storage service automatically injected
    if storage:
        result["services"]["storage"] = "Storage service connected"
    
    # OAuth service automatically injected
    if oauth_service:
        try:
            providers = await oauth_service.get_available_providers()
            result["services"]["oauth"] = f"OAuth providers: {providers}"
        except Exception as e:
            result["services"]["oauth"] = f"OAuth error: {e}"
    
    return result
```

### 4. Run the Agent

```bash
# Run locally with dependency injection (default)
fiber activate --input-data '{"query": "test"}' ./my_agent.py

# Run against local server API
fiber activate --input-data '{"query": "test"}' ./my_agent.py --to-instance default

# Run against remote server
fiber activate --input-data '{"query": "test"}' ./my_agent.py --to-instance "production"

# Run with verbose output to see injected services and routing
fiber activate --verbose --input-data '{"query": "test"}' ./my_agent.py --to-instance local
```

## CLI Usage

### Basic Commands

```bash
# Activate an agent (local direct execution - default)
fiber activate --input-data '{"key": "value"}' ./agent.py

# Activate against local server API
fiber activate --input-data '{"key": "value"}' ./agent.py --to-instance default

# Activate against remote server
fiber activate --input-data '{"key": "value"}' ./agent.py --to-instance "production"

# Verbose output for debugging
fiber activate --verbose --input-data '{"key": "value"}' ./agent.py

# Specify version with instance routing
fiber activate --version "2.0.0" --input-data '{"key": "value"}' ./agent.py --to-instance "production"
```

### Web Server Commands

```bash
# Start the FiberWise web server (default: localhost:8000)
fiber start

# Start with custom host and port
fiber start --host 0.0.0.0 --port 3000

# Start with development features
fiber start --reload --no-browser

```

#### Start Command Options

- `--host`: Host address to bind to (default: 127.0.0.1)
- `--port`: Port number to use (default: 8000)  
- `--reload`: Enable auto-reload for development
- `--no-browser`: Disable automatic browser opening

### Account Management Commands

The account management system integrates with `fiberwise-common` to store configurations and providers in the database for dependency injection.

```bash
# Login with configuration file
fiber account login --config ./my-config.json

# Add configuration directly
fiber account add-config --name "prod" --api-key "your-key" --base-url "https://api.fiberwise.ai" --set-default

# Import providers from app (for dependency injection)
fiber account import-providers --app-id your-app-id --default

# List providers (local database)
fiber account list-providers --to-instance local

# List providers (remote server)
fiber account list-providers --to-instance "production"

# View specific provider details
fiber account list-providers --provider-id provider-uuid --format detailed --to-instance local
```

#### Account Configuration Options

- `--name`: Unique configuration profile name
- `--api-key`: FiberWise API key for accessing platform services
- `--base-url`: API base URL (default: https://api.fiberwise.ai)
- `--set-default`: Mark this configuration as the default
- `--config`: Path to JSON configuration file for login command

#### Provider Import Options

- `--app-id`: Import providers from specific app ID
- `--app-dir`: Application directory (default: current directory)
- `--default`: Set first imported provider as default for dependency injection
- `--format`: Output format (basic, detailed, json)
- `--save-to-file`: Save provider information to file

**Configuration File Format**:
```json
{
  "config_name": "my-config",
  "fiberwise_api_key": "your-api-key",
  "fiberwise_base_url": "https://api.fiberwise.ai"
}
```

### Instance Routing (New Feature)

The CLI now supports routing commands to different execution environments:

```bash
# Local direct database access (fastest - default)
fiber activate ./agent.py --to-instance local
fiber functions list --to-instance local  
fiber account list-providers --to-instance local

# Local server API (for testing server functionality)
fiber activate ./agent.py --to-instance default
fiber account list-providers --to-instance default

# Remote server API (for production deployment)
fiber activate ./agent.py --to-instance "production"
fiber account list-providers --to-instance "production"
```

**Configuration Setup:**
```bash
# Add remote server configuration
fiber account add-config \
  --name "production" \
  --api-key "prod-api-key" \
  --base-url "https://prod.fiberwise.ai"

# List all configurations
fiber account list-configs

# Use remote configuration
fiber activate ./agent.py --to-instance "production" --verbose
```

For detailed instance routing documentation, see: [`CLI_INSTANCE_ROUTING_GUIDE.md`](../CLI_INSTANCE_ROUTING_GUIDE.md)

### Input Data

```bash
# JSON object
fiber activate --input-data '{"query": "test", "limit": 10}' ./agent.py

# Simple string (auto-wrapped)
fiber activate --input-data "simple input" ./agent.py

# With instance routing
fiber activate --input-data '{"query": "test"}' ./agent.py --to-instance "production"
```

## Features

- **✨ Dependency Injection**: Automatic service injection into agents (FiberApp SDK, LLM, OAuth, Storage)
- **🌐 Instance Routing**: Route commands to local, default server, or remote instances with `--to-instance`
- **⚙️ Account Management**: Centralized configuration management with database integration via `fiberwise-common`
- **🔧 Provider Configuration**: Import and manage LLM, OAuth, and storage providers for automatic injection
- **🚀 Agent Activation System**: Register, version, and execute agents with full lifecycle management
- **📊 Activation Tracking**: Complete execution history stored in `agent_activations` table
- **🔧 Service Registry**: Centralized service management with automatic discovery and injection
- **📊 Multi-Database Support**: SQLite, DuckDB, MySQL, PostgreSQL with automatic migrations
- **🌐 CLI Interface**: Comprehensive command-line tools for agent development and deployment
- **💻 Web Interface**: Built-in web server with real-time agent monitoring and management
- **🔐 OAuth Integration**: Built-in OAuth provider support (Google, GitHub, etc.) with token management
- **💾 Storage Providers**: Local, S3, Azure Blob, Google Cloud Storage with unified interface
- **📝 LLM Integration**: Multi-provider LLM support (OpenAI, Anthropic, etc.) with automatic configuration
- **🔄 Real-time Updates**: WebSocket-based real-time activation status and logging
- **📈 Comprehensive Logging**: Detailed execution logs with structured output and debugging support

### Service Injection Details

**Understanding Activations**: In FiberWise, "activations" and "agent activations" refer to the same concept - they are execution instances of agents stored in the `agent_activations` database table. Each activation represents a single run of an agent with specific input data and injected services.

The dependency injection system automatically provides services based on agent method signatures:

- **`fiber` / `fiber_app`**: Core platform service with data, agents, functions, storage
- **`llm_service` / `llm_provider_service` / `llm`**: Language model service for AI operations  
- **`oauth_service` / `oauth` / `credentials`**: Authentication and credential management
- **`storage` / `agent_storage` / `storage_provider`**: Direct file and blob storage access

**Service Configuration**: Services are configured through the account management system and stored in `fiberwise-common` database:
- LLM providers stored in `provider_defaults` table with type 'llm'
- OAuth providers in `oauth_providers` table linked via `app_oauth_provider_links`
- Storage providers configured per app with appropriate credentials
- API keys managed through `account_configs` for FiberApp integration

### Agent Types

The CLI automatically detects:
- **Agents**: Classes inheriting from `FiberAgent` or `Agent`
- **Functions**: Standalone function-based agents
- **Pipelines**: Multi-step processing chains
- **Workflows**: Complex orchestration patterns

### Database Support

Built-in support for multiple database providers:
- **SQLite**: Default, no additional dependencies
- **DuckDB**: `pip install duckdb`
- **MySQL**: `pip install mysql-connector-python`
- **PostgreSQL**: `pip install psycopg2-binary`

## Documentation

### Core Documentation
- **[Getting Started with Dependency Injection](../GETTING_STARTED_DEPENDENCY_INJECTION.md)** - Complete guide to the dependency injection system
- **[Account Management Guide](../docs-bin/account_README.md)** - Account configuration and provider management
- **[Start Command Guide](docs/START_COMMAND_GUIDE.md)** - Web server configuration and deployment
- **[CLI Commands Reference](../docs-bin/commands/readme.md)** - Complete CLI command documentation

### Provider & Service Configuration  
- **[Account Commands](../docs-bin/commands/account/account.md)** - Account management CLI reference
- **[OAuth Provider Setup](../docs-bin/commands/account/oauth.md)** - OAuth provider configuration
- **[App OAuth Management](../docs-bin/commands/app/oauth.md)** - Application-level OAuth setup
- **[Activation System Analysis](../ACTIVATION_SYSTEM_ANALYSIS.md)** - Deep dive into the activation system

### SDK Integration  
- **[FiberWise SDK Documentation](../fiber-sdk-python/fiberwise-sdk/DOCUMENTATION.md)** - Full SDK reference
- **[Agent Development Guide](examples/)** - Example agents and patterns

### Database & Migration
- **[Migration Plan](../docs-bin/FIBER_TO_FIBERWISE_MIGRATION_PLAN.md)** - FiberWise-Common integration plan
- **[Service Extraction Plan](../docs-bin/SERVICE_EXTRACTION_PLAN.md)** - Service architecture documentation

### Legacy Documentation
- **[Agent Dependency Injection Guide](./AGENT_DEPENDENCY_INJECTION.md)**: Legacy agent injection patterns
- **[Database Configuration](#database-support)**: Multi-database setup and configuration
- **[Start Command Testing](./tests/README_START_COMMAND_TESTS.md)**: Web server test documentation

## Testing

### Quick Start
```bash
# Run all working tests (22+ tests)
python -m pytest tests/test_start_command.py tests/test_web_app.py tests/test_activation_service.py -v

# Run complete test suite
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ --cov=fiberwise --cov-report=html
```

### Test Documentation
- **[Complete Test Guide](./tests/README.md)**: Comprehensive testing documentation
- **[Test Status](./tests/TEST_STATUS.md)**: Current test status and quick commands
- **[Start Command Tests](./tests/README_START_COMMAND_TESTS.md)**: Detailed start command test documentation

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test modules
python -m pytest tests/test_start_command.py -v
python -m pytest tests/test_activation_service.py -v

# Run with coverage
python -m pytest tests/ --cov=fiberwise --cov-report=html
```

### Test Coverage

- **Start Command**: 7 comprehensive tests covering CLI functionality, port handling, and server startup
- **Activation Service**: Full lifecycle testing with dependency injection
- **Web Application**: FastAPI endpoint testing with CORS validation
- **CLI Integration**: End-to-end command line interface testing

### Test Structure

- `tests/test_start_command.py`: Web server startup and CLI option validation
- `tests/test_activation_service.py`: Agent registration and execution testing  
- `tests/test_web_app.py`: FastAPI web application endpoint testing
- `tests/test_cli_integration.py`: CLI command integration testing

## Architecture

### Core Components

1. **ActivationService**: Manages agent lifecycle (registration, versioning, execution)
2. **AccountService**: Handles configuration management, API keys, and provider imports (via `fiberwise-common`)
3. **DatabaseService**: Handles data persistence across multiple database types
4. **CLI Commands**: User interface for agent activation and management
5. **Dependency Injection**: Automatic service resolution and injection based on stored provider configurations

### Integration with FiberWise-Common

The system integrates with `fiberwise-common` for:
- **Database Operations**: Shared database provider and query adapters
- **Service Registry**: Centralized service management with dependency injection
- **Account Management**: Configuration storage in database tables
- **Provider Management**: LLM, OAuth, and storage provider configurations

### Agent Lifecycle

1. **Detection**: CLI analyzes file content to determine activation type
2. **Registration**: Agent metadata is stored with version tracking in `agents` table
3. **Account Integration**: System retrieves API keys and provider configs from `account_configs` 
4. **Dependency Resolution**: Services are initialized based on stored provider configurations
5. **Activation Creation**: New record created in `agent_activations` table with status tracking
6. **Execution**: Agent runs with injected dependencies from configured providers
7. **Results**: Output is captured and stored in activation record

## Provider Configuration & Dependency Injection Setup

### Setting Up Default Providers

The account management system stores provider configurations in the database for automatic dependency injection:

```bash
# 1. Configure your FiberWise account
fiber account add-config --name "prod" --api-key "your-api-key" --base-url "https://api.fiberwise.ai" --set-default

# 2. Import providers from your app (for LLM, OAuth, Storage services)
fiber account import-providers --app-id your-app-id --default

# 3. Verify provider configuration
fiber account list-providers --format detailed
```

### Supported Provider Types

#### LLM Providers
- **OpenAI**: GPT-3.5, GPT-4, ChatGPT models
- **Anthropic**: Claude models
- **Google**: Gemini models  
- **Azure OpenAI**: Enterprise OpenAI models

#### OAuth Providers
- **Google**: Gmail, Drive, Calendar access
- **Microsoft**: Office 365, Teams, OneDrive
- **GitHub**: Repository and user data access
- **Custom**: Any OAuth 2.0 compatible provider

#### Storage Providers
- **Local**: File system storage
- **AWS S3**: Amazon Simple Storage Service
- **Azure Blob**: Microsoft Azure Blob Storage
- **Google Cloud Storage**: Google Cloud Platform storage
- **Cloudflare R2**: Cloudflare object storage

### Provider Configuration Files

When importing providers, the system creates configuration files in `~/.fiberwise/providers/`:

```json
{
  "provider_id": "google-llm-provider",
  "provider_type": "llm",
  "name": "Google Gemini",
  "config": {
    "api_key": "encrypted_key_reference",
    "model": "gemini-pro",
    "base_url": "https://generativelanguage.googleapis.com"
  },
  "is_default": true,
  "created_at": "2025-08-02T10:00:00Z"
}
```

### Default Provider Management

```bash
# Set default LLM provider
fiber account provider default "Google Gemini"

# List providers by type
fiber account provider list --type llm
fiber account provider list --type oauth
fiber account provider list --type storage

# View all provider types
fiber account provider list --format detailed
```

## Examples

### Basic Agent
See `test_fiber_app_agent.py` for a complete working example.

### Agent with Multiple Services
```python
from fiberwise_sdk import FiberAgent

class AdvancedAgent(FiberAgent):
    def get_dependencies(self):
        return {
            'fiber_app': 'FiberApp',
            'llm_service': 'LLMService',
            'storage': 'StorageService'
        }
    
    def run_agent(self, input_data, fiber_app=None, llm_service=None, storage=None):
        # Use multiple injected services
        if fiber_app and llm_service:
            data = fiber_app.data.query("SELECT * FROM context")
            response = llm_service.generate(f"Analyze: {data}")
            
            if storage:
                storage.save("analysis.json", response)
                
            return {"status": "success", "analysis": response}
        
        return {"status": "limited", "message": "Required services not available"}
```

### Configuration-Based Agent
```python
def run_agent(input_data, fiber=None, llm_service=None, oauth_service=None, storage=None):
    """Agent that uses providers configured via account management"""
    
    result = {"input": input_data, "services_available": []}
    
    # FiberApp service (configured via account add-config)
    if fiber:
        result["services_available"].append("FiberApp")
        result["app_data"] = fiber.data.query("SELECT COUNT(*) as count FROM agents")
    
    # LLM service (configured via import-providers --default)
    if llm_service:
        result["services_available"].append("LLM")
        result["ai_response"] = llm_service.generate("Summarize the input data")
    
    # OAuth service (imported from app providers)
    if oauth_service:
        result["services_available"].append("OAuth")
        result["oauth_providers"] = oauth_service.get_available_providers()
    
    # Storage service (from provider configuration)
    if storage:
        result["services_available"].append("Storage")
        storage.save("execution_log.json", result)
    
    return result
```
See `test_fiber_app_agent.py` for a complete working example.

### Agent with Multiple Services
```python
from fiberwise_sdk import FiberAgent

class AdvancedAgent(FiberAgent):
    def get_dependencies(self):
        return {
            'fiber_app': 'FiberApp',
            'llm_service': 'LLMService',
            'storage': 'StorageService'
        }
    
    def run_agent(self, input_data, fiber_app=None, llm_service=None, storage=None):
        # Use multiple injected services
        if fiber_app and llm_service:
            data = fiber_app.data.query("SELECT * FROM context")
            response = llm_service.generate(f"Analyze: {data}")
            
            if storage:
                storage.save("analysis.json", response)
                
            return {"status": "success", "analysis": response}
        
        return {"status": "limited", "message": "Required services not available"}
```

## Troubleshooting

### Common Issues

**Account Configuration Issues**:
- **Configuration not found**: Use `fiber account list-providers` to verify configs exist
- **API key invalid**: Verify key with `fiber account add-config --name test --api-key your-key --base-url https://api.fiberwise.ai`
- **Provider import fails**: Ensure app-id exists and you have proper permissions

**Dependency Injection Issues**:
- **Services are None**: Check provider configuration with `fiber account list-providers --format detailed`
- **SDK Not Found**: Install with `pip install fiberwise-sdk`
- **Agent Not Detected**: Ensure proper inheritance from `FiberAgent`

**Database Connection Issues**:
- **Database Errors**: Install required database drivers
- **Migration Issues**: Run `fiber start` to initialize database tables
- **fiberwise-common Integration**: Ensure `fiberwise-common` is properly installed

### Debug Mode

Use `--verbose` flag for detailed execution information:
```bash
fiber activate --verbose --input-data '{"debug": true}' ./agent.py
```

### Configuration Verification

```bash
# Check account configuration
fiber account list-providers --format json

# Verify default provider
cat ~/.fiberwise/default_provider.json

# Test database connection
fiber start --verbose
```

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Creating New Agents
See the [Agent Dependency Injection Guide](./AGENT_DEPENDENCY_INJECTION.md) for detailed instructions.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

[Add your license information here]

---

Note: For database providers other than SQLite, you'll need to manually install:
- duckdb package for DuckDB support
- mysql-connector-python for MySQL support  
- psycopg2-binary for PostgreSQL support
