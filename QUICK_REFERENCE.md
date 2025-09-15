# FiberWise Agent Quick Reference

## Agent Template

```python
from fiberwise_sdk import FiberAgent

class MyAgent(FiberAgent):
    def get_dependencies(self):
        """Declare services this agent needs"""
        return {
            'fiber_app': 'FiberApp',
            # Add other services as needed
        }
    
    def run_agent(self, input_data, fiber_app=None, **kwargs):
        """Main execution with dependency injection"""
        # Always check for None services
        if fiber_app:
            # Use platform services
            result = fiber_app.data.query("SELECT * FROM table")
            return {"status": "success", "data": result}
        else:
            # Graceful fallback
            return {"status": "limited", "message": "SDK not available"}
```

## Available Services

| Service | Type | Description |
|---------|------|-------------|
| `fiber_app` | `FiberApp` | Core platform service |
| `llm_service` | `LLMService` | Language model operations |
| `oauth_service` | `OAuthService` | Authentication |
| `storage` | `StorageService` | File/blob storage |

## FiberApp Sub-Services

```python
def run_agent(self, input_data, fiber_app=None):
    if fiber_app:
        # Data operations
        fiber_app.data.query("SELECT * FROM users")
        fiber_app.data.store({"key": "value"})
        
        # Agent invocation
        fiber_app.agents.invoke("other_agent", data)
        
        # Functions (if available)
        fiber_app.func.call("function_name", params)
        
        # Storage
        fiber_app.storage.upload("file.txt", content)
        
        # Platform info
        info = fiber_app.get_platform_info()
```

## CLI Commands

```bash
# Basic activation
fiber activate --input-data '{"key": "value"}' ./agent.py

# With debugging
fiber activate --verbose --input-data '{"key": "value"}' ./agent.py

# Specify version
fiber activate --version "1.0.0" --input-data '{"key": "value"}' ./agent.py
```

## Error Handling Pattern

```python
def run_agent(self, input_data, fiber_app=None):
    try:
        # Validate inputs
        if not input_data:
            return {"status": "error", "message": "No input provided"}
        
        # Check service availability
        if not fiber_app:
            return {"status": "error", "message": "FiberApp required"}
        
        # Main logic here
        result = process_data(input_data, fiber_app)
        
        return {"status": "success", "result": result}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

## SDK Import Pattern

```python
try:
    from fiberwise_sdk import FiberAgent
    HAS_SDK = True
except ImportError:
    FiberAgent = object
    HAS_SDK = False

class MyAgent(FiberAgent):
    def run_agent(self, input_data, **kwargs):
        if not HAS_SDK:
            return {"status": "limited", "message": "SDK not available"}
        # Implementation...
```

## Debugging Tips

1. **Use verbose mode**: `--verbose` flag shows detailed execution
2. **Check SDK availability**: Print `HAS_SDK` status
3. **Validate services**: Always check if injected services are not None
4. **Log service types**: Print `type(service)` to verify injection
5. **Test graceful degradation**: Ensure agents work without SDK

## Common Patterns

### Simple Data Agent
```python
def run_agent(self, input_data, fiber_app=None):
    if fiber_app:
        return fiber_app.data.query(input_data.get("query"))
    return {"status": "error", "message": "Data service required"}
```

### AI-Enhanced Agent
```python
def run_agent(self, input_data, fiber_app=None, llm_service=None):
    base_result = process_basic(input_data)
    
    if llm_service:
        enhanced = llm_service.generate(f"Enhance: {base_result}")
        return {"status": "enhanced", "result": enhanced}
    
    return {"status": "basic", "result": base_result}
```

### Multi-Agent Orchestrator
```python
def run_agent(self, input_data, fiber_app=None):
    if not fiber_app:
        return {"status": "error", "message": "Platform access required"}
    
    # Invoke multiple agents
    agent1_result = fiber_app.agents.invoke("analyzer", input_data)
    agent2_result = fiber_app.agents.invoke("processor", agent1_result)
    
    return {"status": "orchestrated", "results": [agent1_result, agent2_result]}
```
