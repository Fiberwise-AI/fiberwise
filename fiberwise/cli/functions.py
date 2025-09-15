#!/usr/bin/env python3
"""
CLI commands for FiberWise Functions and Pipelines
Direct service integration without API calls
"""

import json
import click
import os
import asyncio
import uuid
import sys
from pathlib import Path
from typing import Dict, Any, Optional



from fiberwise_common import DatabaseProvider
from fiberwise_common.entities.config import Config
from fiberwise_common.database import SQLiteProvider


async def _get_database_provider(config: Config, verbose: bool = False) -> DatabaseProvider:
    """Get database provider from config"""
    try:
        db_provider = config.db_provider
        await db_provider.connect()
        if verbose:
            click.echo("[OK] Connected to database")
        return db_provider
    except Exception as e:
        click.echo(f"Error connecting to database: {e}", err=True)
        raise


@click.group()
def functions():
    """Function and pipeline management commands"""
    pass


@functions.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--search', help="Search functions by name or description")
@click.option('--type', 'function_type', help="Filter by function type (utility, transform, support_agent)")
@click.option('--limit', default=20, help="Maximum number of functions to show")
@click.option('--to-instance', default='local', help="Target FiberWise instance: 'local' for direct access, or config name for remote API")
def list(verbose, search, function_type, limit, to_instance):
    """List all functions in the system"""
    asyncio.run(_list_functions_async(verbose, search, function_type, limit, to_instance))


async def _list_functions_async(verbose: bool, search: Optional[str], function_type: Optional[str], limit: int, to_instance: str):
    """List functions using direct database access"""
    
    # Route based on to_instance parameter
    if to_instance != 'local':
        click.echo(f"🌐 Remote instance access for '{to_instance}' not yet implemented.", err=True)
        click.echo("💡 Remote function listing will be available in a future update.", err=True)
        click.echo("🏠 Use --to-instance local for local database access.", err=True)
        return
    
    config = Config()
    db_provider = None
    
    try:
        db_provider = await _get_database_provider(config, verbose)
        
        # Build query with filters
        query_parts = ["SELECT function_id, name, description, function_type, is_system, created_at FROM functions"]
        params = []
        
        where_clauses = []
        if search:
            where_clauses.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        if function_type:
            where_clauses.append("function_type = ?")
            params.append(function_type)
        
        if where_clauses:
            query_parts.append("WHERE " + " AND ".join(where_clauses))
        
        query_parts.append("ORDER BY name ASC")
        query_parts.append(f"LIMIT {limit}")
        
        query = " ".join(query_parts)
        
        functions = await db_provider.fetch_all(query, *params)
        
        if not functions:
            click.echo("No functions found")
            return
        
        click.echo(f"\nFound {len(functions)} function(s):")
        click.echo("-" * 80)
        
        for func in functions:
            system_flag = " [SYSTEM]" if func['is_system'] else ""
            click.echo(f"• {func['name']} ({func['function_type']}){system_flag}")
            click.echo(f"  ID: {func['function_id']}")
            if func['description']:
                click.echo(f"  Description: {func['description']}")
            if verbose:
                click.echo(f"  Created: {func['created_at']}")
            click.echo()
        
    except Exception as e:
        click.echo(f"Error listing functions: {e}", err=True)
    finally:
        if db_provider:
            await db_provider.disconnect()


@functions.command()
@click.argument('function_id', required=True)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def show(function_id, verbose):
    """Show detailed information about a function"""
    asyncio.run(_show_function_async(function_id, verbose))


async def _show_function_async(function_id: str, verbose: bool):
    """Show function details using direct database access"""
    config = Config()
    db_provider = None
    
    try:
        db_provider = await _get_database_provider(config, verbose)
        
        # Get function details
        func = await db_provider.fetch_one(
            "SELECT * FROM functions WHERE function_id = ? OR name = ?", 
            function_id, function_id
        )
        
        if not func:
            click.echo(f"Function not found: {function_id}")
            return
        
        click.echo(f"\nFunction: {func['name']}")
        click.echo("=" * 50)
        click.echo(f"ID: {func['function_id']}")
        click.echo(f"Type: {func['function_type']}")
        click.echo(f"System: {'Yes' if func['is_system'] else 'No'}")
        click.echo(f"Async: {'Yes' if func['is_async'] else 'No'}")
        
        if func['description']:
            click.echo(f"Description: {func['description']}")
        
        # Parse and display schemas
        if func['input_schema']:
            try:
                input_schema = json.loads(func['input_schema'])
                click.echo(f"\nInput Schema:")
                click.echo(json.dumps(input_schema, indent=2))
            except json.JSONDecodeError:
                click.echo(f"Input Schema: {func['input_schema']}")
        
        if func['output_schema']:
            try:
                output_schema = json.loads(func['output_schema'])
                click.echo(f"\nOutput Schema:")
                click.echo(json.dumps(output_schema, indent=2))
            except json.JSONDecodeError:
                click.echo(f"Output Schema: {func['output_schema']}")
        
        if verbose and func['implementation']:
            click.echo(f"\nImplementation:")
            click.echo("-" * 30)
            click.echo(func['implementation'])
        
        # Show recent executions
        executions = await db_provider.fetch_all(
            """SELECT execution_id, status, started_at, completed_at, error 
               FROM function_executions 
               WHERE function_id = ? 
               ORDER BY started_at DESC LIMIT 5""",
            func['function_id']
        )
        
        if executions:
            click.echo(f"\nRecent Executions (Last 5):")
            click.echo("-" * 30)
            for exe in executions:
                status_icon = "[OK]" if exe['status'] == 'completed' else "[FAIL]" if exe['status'] == 'failed' else "[RUNNING]"
                click.echo(f"{status_icon} {exe['execution_id'][:8]}... - {exe['status']} - {exe['started_at']}")
                if exe['error'] and verbose:
                    click.echo(f"    Error: {exe['error']}")
        
    except Exception as e:
        click.echo(f"Error showing function: {e}", err=True)
    finally:
        if db_provider:
            await db_provider.disconnect()


@functions.command()
@click.argument('function_id', required=True)
@click.option('--input-data', help="Input data as JSON string")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--to-instance', default='local', help="Target FiberWise instance: 'local' for direct access, or config name for remote API")
def execute(function_id, input_data, verbose, to_instance):
    """Execute a function with optional input data"""
    asyncio.run(_execute_function_async(function_id, input_data, verbose, to_instance))


@functions.command()
@click.argument('function_ids', required=True, nargs=-1)
@click.option('--input-data', help="Input data as JSON string")
@click.option('--context', help="Shared context as JSON string (e.g., chat_id, session_id)")
@click.option('--coordination-mode', type=click.Choice(['sequential', 'parallel', 'chain']), default='sequential', 
              help="How to coordinate execution: sequential (one after another), parallel (all at once), chain (output of one feeds to next)")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def execute_multi(function_ids, input_data, context, coordination_mode, verbose):
    """Execute multiple functions with coordination"""
    asyncio.run(_execute_multi_function_async(function_ids, input_data, context, coordination_mode, verbose))


async def _execute_multi_function_async(function_ids: tuple, input_data: Optional[str], context: Optional[str], coordination_mode: str, verbose: bool):
    """Execute multiple functions with coordination using direct service access"""
    config = Config()
    db_provider = None
    
    try:
        db_provider = await _get_database_provider(config, verbose)
        
        # Import the function service
        from api.services.function_service import FunctionService
        from api.schemas.user import User
        
        # Create a mock user for CLI execution
        cli_user = User(id=1, username="cli-user", email="cli@example.com")
        
        # Create function service
        function_service = FunctionService(db_provider)
        
        # Parse input data
        parsed_input = {}
        if input_data:
            try:
                parsed_input = json.loads(input_data)
                if verbose:
                    click.echo(f"Input data: {json.dumps(parsed_input, indent=2)}")
            except json.JSONDecodeError as e:
                click.echo(f"Invalid JSON input data: {e}", err=True)
                return
        
        # Parse context data
        parsed_context = {}
        if context:
            try:
                parsed_context = json.loads(context)
                if verbose:
                    click.echo(f"Shared context: {json.dumps(parsed_context, indent=2)}")
            except json.JSONDecodeError as e:
                click.echo(f"Invalid JSON context data: {e}", err=True)
                return
        
        if verbose:
            click.echo(f"Executing {len(function_ids)} functions in {coordination_mode} mode")
            click.echo(f"Functions: {', '.join(function_ids)}")
        
        results = []
        current_input = parsed_input.copy()
        
        if coordination_mode == 'parallel':
            # Execute all functions in parallel
            import asyncio
            tasks = []
            for func_id in function_ids:
                task = function_service.execute_function(
                    app_id=None,  # CLI execution
                    function_id=func_id,
                    input_data={**current_input, **parsed_context},
                    user=cli_user
                )
                tasks.append(task)
            
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(parallel_results):
                if isinstance(result, Exception):
                    click.echo(f"Function {function_ids[i]} failed: {result}", err=True)
                    results.append({"status": "error", "function_id": function_ids[i], "error": str(result)})
                else:
                    results.append({"function_id": function_ids[i], **result})
                    
        elif coordination_mode == 'chain':
            # Execute functions in sequence, chaining output to input
            for func_id in function_ids:
                if verbose:
                    click.echo(f"\n--- Executing {func_id} ---")
                
                result = await function_service.execute_function(
                    app_id=None,  # CLI execution
                    function_id=func_id,
                    input_data={**current_input, **parsed_context},
                    user=cli_user
                )
                
                if result:
                    results.append({"function_id": func_id, **result})
                    
                    # Use output as input for next function
                    if result.get('result'):
                        current_input = result['result']
                        if verbose:
                            click.echo(f"Chaining output to next function: {json.dumps(current_input, indent=2)}")
                else:
                    click.echo(f"Function {func_id} failed, breaking chain", err=True)
                    break
                    
        else:  # sequential mode
            # Execute functions one after another with same input
            for func_id in function_ids:
                if verbose:
                    click.echo(f"\n--- Executing {func_id} ---")
                
                result = await function_service.execute_function(
                    app_id=None,  # CLI execution
                    function_id=func_id,
                    input_data={**current_input, **parsed_context},
                    user=cli_user
                )
                
                if result:
                    results.append({"function_id": func_id, **result})
                else:
                    click.echo(f"Function {func_id} failed", err=True)
                    results.append({"status": "error", "function_id": func_id})
        
        # Display results
        click.echo(f"\n[SUCCESS] Multi-function execution completed!")
        click.echo("=" * 60)
        
        for i, result in enumerate(results):
            click.echo(f"\nFunction {i+1}: {result.get('function_id', 'unknown')}")
            click.echo("-" * 40)
            
            if verbose and result.get('execution_id'):
                click.echo(f"Execution ID: {result.get('execution_id')}")
                click.echo(f"Status: {result.get('status')}")
                click.echo(f"Started: {result.get('started_at')}")
                if result.get('completed_at'):
                    click.echo(f"Completed: {result.get('completed_at')}")
            
            if result.get('result'):
                click.echo("Result:")
                click.echo(json.dumps(result['result'], indent=2))
            
            if result.get('error'):
                click.echo(f"Error: {result['error']}", err=True)
        
        # Summary statistics
        successful = len([r for r in results if r.get('status') != 'error'])
        failed = len(results) - successful
        
        click.echo(f"\nSummary: {successful} successful, {failed} failed out of {len(results)} total")
        
    except Exception as e:
        click.echo(f"Error executing multi-function: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc())
    finally:
        if db_provider:
            await db_provider.disconnect()


async def _execute_function_async(function_id: str, input_data: Optional[str], verbose: bool, to_instance: str):
    """Execute function using direct service access"""
    
    # Route based on to_instance parameter
    if to_instance != 'local':
        click.echo(f"🌐 Remote function execution for '{to_instance}' not yet implemented.", err=True)
        click.echo("💡 Remote function execution will be available in a future update.", err=True)
        click.echo("🏠 Use --to-instance local for local database access.", err=True)
        return
    
    config = Config()
    db_provider = None
    
    try:
        db_provider = await _get_database_provider(config, verbose)
        
        # Import the function service
        from api.services.function_service import FunctionService
        from api.schemas.user import User
        
        # Create a mock user for CLI execution
        cli_user = User(id=1, username="cli-user", email="cli@example.com")
        
        # Create function service
        function_service = FunctionService(db_provider)
        
        # Parse input data
        parsed_input = {}
        if input_data:
            try:
                parsed_input = json.loads(input_data)
                if verbose:
                    click.echo(f"Input data: {json.dumps(parsed_input, indent=2)}")
            except json.JSONDecodeError as e:
                click.echo(f"Invalid JSON input data: {e}", err=True)
                return
        
        if verbose:
            click.echo(f"Executing function: {function_id}")
        
        # Execute the function
        result = await function_service.execute_function(
            app_id=None,  # CLI execution
            function_id=function_id,
            input_data=parsed_input,
            user=cli_user
        )
        
        if result:
            click.echo("\n[SUCCESS] Function executed successfully!")
            click.echo("-" * 40)
            
            if verbose:
                click.echo(f"Execution ID: {result.get('execution_id')}")
                click.echo(f"Status: {result.get('status')}")
                click.echo(f"Started: {result.get('started_at')}")
                if result.get('completed_at'):
                    click.echo(f"Completed: {result.get('completed_at')}")
            
            if result.get('result'):
                click.echo("Result:")
                click.echo(json.dumps(result['result'], indent=2))
            
            if result.get('error'):
                click.echo(f"Error: {result['error']}", err=True)
        else:
            click.echo("Function execution failed", err=True)
        
    except Exception as e:
        click.echo(f"Error executing function: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc())
    finally:
        if db_provider:
            await db_provider.disconnect()


@functions.command()
@click.argument('name', required=True)
@click.option('--description', help="Function description")
@click.option('--type', 'function_type', default='utility', help="Function type (utility, transform, support_agent)")
@click.option('--file', 'code_file', help="Python file containing the function implementation")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def create(name, description, function_type, code_file, verbose):
    """Create a new function from a Python file"""
    asyncio.run(_create_function_async(name, description, function_type, code_file, verbose))


async def _create_function_async(name: str, description: Optional[str], function_type: str, code_file: Optional[str], verbose: bool):
    """Create function using direct service access"""
    config = Config()
    db_provider = None
    
    try:
        db_provider = await _get_database_provider(config, verbose)
        
        # Import the function service
        from api.services.function_service import FunctionService
        
        # Create function service
        function_service = FunctionService(db_provider)
        
        # Read implementation from file if provided
        implementation = None
        if code_file:
            if not os.path.exists(code_file):
                click.echo(f"File not found: {code_file}", err=True)
                return
            
            with open(code_file, 'r') as f:
                implementation = f.read()
            
            if verbose:
                click.echo(f"Read implementation from: {code_file}")
        else:
            # Default simple implementation
            implementation = '''def run(input_data):
    """Default function implementation"""
    return {"status": "success", "input": input_data}'''
        
        # Create function data
        function_data = {
            "name": name,
            "description": description or f"Function created via CLI: {name}",
            "function_type": function_type,
            "input_schema": {
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Input data"}
                }
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "result": {"type": "object"}
                }
            },
            "implementation": implementation,
            "is_async": False,
            "is_system": False
        }
        
        if verbose:
            click.echo(f"Creating function: {name}")
            click.echo(f"Type: {function_type}")
            if description:
                click.echo(f"Description: {description}")
        
        # Create the function
        created_function = await function_service.create_function(function_data)
        
        if created_function:
            click.echo("\n[SUCCESS] Function created successfully!")
            click.echo("-" * 40)
            click.echo(f"Name: {created_function['name']}")
            click.echo(f"ID: {created_function['function_id']}")
            click.echo(f"Type: {created_function['function_type']}")
            
            if verbose:
                click.echo(f"Created at: {created_function.get('created_at')}")
                click.echo("\nYou can now execute it with:")
                click.echo(f"  fiber functions execute {created_function['function_id']} --input-data '{{}}'")
        else:
            click.echo("Function creation failed", err=True)
        
    except Exception as e:
        click.echo(f"Error creating function: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc())
    finally:
        if db_provider:
            await db_provider.disconnect()


@functions.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--limit', default=20, help="Maximum number of pipelines to show")
def list_pipelines(verbose, limit):
    """List all pipelines in the system"""
    asyncio.run(_list_pipelines_async(verbose, limit))


async def _list_pipelines_async(verbose: bool, limit: int):
    """List pipelines using direct database access"""
    config = Config()
    db_provider = None
    
    try:
        db_provider = await _get_database_provider(config, verbose)
        
        pipelines = await db_provider.fetch_all(
            """SELECT pipeline_id, name, description, is_active, created_at 
               FROM agent_pipelines 
               ORDER BY name ASC 
               LIMIT ?""",
            limit
        )
        
        if not pipelines:
            click.echo("No pipelines found")
            return
        
        click.echo(f"\nFound {len(pipelines)} pipeline(s):")
        click.echo("-" * 80)
        
        for pipeline in pipelines:
            active_flag = " [ACTIVE]" if pipeline['is_active'] else " [INACTIVE]"
            click.echo(f"• {pipeline['name']}{active_flag}")
            click.echo(f"  ID: {pipeline['pipeline_id']}")
            if pipeline['description']:
                click.echo(f"  Description: {pipeline['description']}")
            if verbose:
                click.echo(f"  Created: {pipeline['created_at']}")
            click.echo()
        
    except Exception as e:
        click.echo(f"Error listing pipelines: {e}", err=True)
    finally:
        if db_provider:
            await db_provider.disconnect()


@functions.command()
@click.argument('pipeline_id', required=True)
@click.option('--input-data', help="Input data as JSON string")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def execute_pipeline(pipeline_id, input_data, verbose):
    """Execute a pipeline with optional input data"""
    asyncio.run(_execute_pipeline_async(pipeline_id, input_data, verbose))


async def _execute_pipeline_async(pipeline_id: str, input_data: Optional[str], verbose: bool):
    """Execute pipeline using direct service access"""
    config = Config()
    db_provider = None
    
    try:
        db_provider = await _get_database_provider(config, verbose)
        
        # Import the pipeline service
        from api.services.pipeline_service import PipelineService
        
        # Parse input data
        parsed_input = {}
        if input_data:
            try:
                parsed_input = json.loads(input_data)
                if verbose:
                    click.echo(f"Input data: {json.dumps(parsed_input, indent=2)}")
            except json.JSONDecodeError as e:
                click.echo(f"Invalid JSON input data: {e}", err=True)
                return
        
        if verbose:
            click.echo(f"Executing pipeline: {pipeline_id}")
        
        # Execute the pipeline
        result = await PipelineService.execute_pipeline(
            pipeline_id=pipeline_id,
            input_data=parsed_input,
            user={'id': 'cli-user'},
            db=db_provider
        )
        
        if result:
            click.echo("\n[SUCCESS] Pipeline execution started!")
            click.echo("-" * 40)
            click.echo(f"Execution ID: {result.get('execution_id')}")
            click.echo(f"Status: {result.get('status')}")
            click.echo(f"Started: {result.get('started_at')}")
            
            if verbose and result.get('input_data'):
                click.echo("Input data:")
                click.echo(json.dumps(json.loads(result['input_data']), indent=2))
            
            click.echo("\nUse 'fiber functions pipeline-status <execution_id>' to check progress")
        else:
            click.echo("Pipeline execution failed", err=True)
        
    except Exception as e:
        click.echo(f"Error executing pipeline: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc())
    finally:
        if db_provider:
            await db_provider.disconnect()


@functions.command()
@click.argument('execution_id', required=True)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def pipeline_status(execution_id, verbose):
    """Check the status of a pipeline execution"""
    asyncio.run(_pipeline_status_async(execution_id, verbose))


@functions.command()
@click.argument('agent_ids', required=True, nargs=-1)
@click.option('--input-data', help="Input data as JSON string")
@click.option('--context', help="Shared context as JSON string (e.g., chat_id, session_id)")
@click.option('--coordination-mode', type=click.Choice(['sequential', 'parallel', 'chain', 'conversation']), default='sequential',
              help="How to coordinate execution: sequential, parallel, chain (output feeds to next), conversation (chat-like activation pattern)")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--to-instance', default='local', help="Target FiberWise instance: 'local' for direct access, or config name for remote API")
def activate_multi(agent_ids, input_data, context, coordination_mode, verbose, to_instance):
    """Activate multiple agents with coordination (similar to activation-chat pattern)"""
    asyncio.run(_activate_multi_agent_async(agent_ids, input_data, context, coordination_mode, verbose, to_instance))


@functions.command()
@click.option('--chat-id', help="Chat/session ID to filter activations")
@click.option('--agent-id', help="Filter by specific agent ID")
@click.option('--limit', default=20, help="Maximum number of activations to show")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def activation_history(chat_id, agent_id, limit, verbose):
    """View activation history for multi-agent conversations"""
    asyncio.run(_activation_history_async(chat_id, agent_id, limit, verbose))


@functions.command()
@click.option('--search', help="Search agents by name or description")
@click.option('--limit', default=20, help="Maximum number of agents to show")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
@click.option('--to-instance', default='local', help="Target FiberWise instance: 'local' for direct access, or config name for remote API")
def list_agents(search, limit, verbose, to_instance):
    """List all available agents in the system"""
    asyncio.run(_list_agents_async(search, limit, verbose, to_instance))


@functions.command()
@click.argument('agent_id', required=True)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def show_agent(agent_id, verbose):
    """Show detailed information about an agent"""
    asyncio.run(_show_agent_async(agent_id, verbose))


@functions.command()
@click.argument('template_name', required=True)
@click.argument('agent_ids', required=True, nargs=-1)
@click.option('--coordination-mode', type=click.Choice(['sequential', 'parallel', 'chain', 'conversation']), default='sequential',
              help="Default coordination mode for this template")
@click.option('--description', help="Description of the workflow template")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def create_workflow(template_name, agent_ids, coordination_mode, description, verbose):
    """Create a reusable multi-agent workflow template"""
    asyncio.run(_create_workflow_async(template_name, agent_ids, coordination_mode, description, verbose))


@functions.command()
@click.argument('template_name', required=True)
@click.option('--input-data', help="Input data as JSON string")
@click.option('--context', help="Execution context as JSON string")
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def run_workflow(template_name, input_data, context, verbose):
    """Execute a saved multi-agent workflow template"""
    asyncio.run(_run_workflow_async(template_name, input_data, context, verbose))


@functions.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def list_workflows(verbose):
    """List all saved workflow templates"""
    asyncio.run(_list_workflows_async(verbose))


async def _create_workflow_async(template_name: str, agent_ids: tuple, coordination_mode: str, description: Optional[str], verbose: bool):
    """Create a workflow template (stored as JSON file)"""
    import os
    import json
    from pathlib import Path
    
    try:
        # Create workflows directory
        workflows_dir = Path.home() / ".fiberwise" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        # Create workflow template
        workflow = {
            "name": template_name,
            "description": description or f"Multi-agent workflow: {template_name}",
            "agent_ids": list(agent_ids),
            "coordination_mode": coordination_mode,
            "created_at": str(uuid.uuid4()),  # Use as timestamp placeholder
            "version": "1.0"
        }
        
        # Save workflow
        workflow_file = workflows_dir / f"{template_name}.json"
        with open(workflow_file, 'w') as f:
            json.dump(workflow, f, indent=2)
        
        click.echo(f"\n[SUCCESS] Workflow template created!")
        click.echo("-" * 40)
        click.echo(f"Name: {template_name}")
        click.echo(f"Agents: {', '.join(agent_ids)}")
        click.echo(f"Coordination: {coordination_mode}")
        click.echo(f"Saved to: {workflow_file}")
        
        if verbose:
            click.echo(f"Description: {description}")
            click.echo("\nExecute with:")
            click.echo(f"  fiber functions run-workflow {template_name} --input-data '{{}}' --verbose")
        
    except Exception as e:
        click.echo(f"Error creating workflow template: {e}", err=True)


async def _run_workflow_async(template_name: str, input_data: Optional[str], context: Optional[str], verbose: bool):
    """Execute a saved workflow template"""
    import json
    from pathlib import Path
    
    try:
        # Load workflow template
        workflows_dir = Path.home() / ".fiberwise" / "workflows"
        workflow_file = workflows_dir / f"{template_name}.json"
        
        if not workflow_file.exists():
            click.echo(f"Workflow template not found: {template_name}")
            click.echo(f"Available templates: {', '.join([f.stem for f in workflows_dir.glob('*.json')])}")
            return
        
        with open(workflow_file, 'r') as f:
            workflow = json.load(f)
        
        if verbose:
            click.echo(f"Executing workflow: {workflow['name']}")
            click.echo(f"Description: {workflow['description']}")
            click.echo(f"Agents: {', '.join(workflow['agent_ids'])}")
            click.echo(f"Coordination: {workflow['coordination_mode']}")
        
        # Execute the workflow using existing multi-agent activation
        await _activate_multi_agent_async(
            tuple(workflow['agent_ids']),
            input_data,
            context,
            workflow['coordination_mode'],
            verbose
        )
        
    except Exception as e:
        click.echo(f"Error running workflow template: {e}", err=True)


async def _list_workflows_async(verbose: bool):
    """List all saved workflow templates"""
    from pathlib import Path
    import json
    
    try:
        workflows_dir = Path.home() / ".fiberwise" / "workflows"
        
        if not workflows_dir.exists():
            click.echo("No workflows directory found. Create workflows with 'fiber functions create-workflow'")
            return
        
        workflow_files = list(workflows_dir.glob("*.json"))
        
        if not workflow_files:
            click.echo("No workflow templates found")
            return
        
        click.echo(f"\nFound {len(workflow_files)} workflow template(s):")
        click.echo("-" * 80)
        
        for workflow_file in workflow_files:
            try:
                with open(workflow_file, 'r') as f:
                    workflow = json.load(f)
                
                click.echo(f"• {workflow['name']} ({workflow['coordination_mode']})")
                click.echo(f"  Agents: {', '.join(workflow['agent_ids'])}")
                if workflow.get('description'):
                    click.echo(f"  Description: {workflow['description']}")
                if verbose:
                    click.echo(f"  File: {workflow_file}")
                    click.echo(f"  Version: {workflow.get('version', '1.0')}")
                click.echo()
                
            except json.JSONDecodeError:
                click.echo(f"• Invalid workflow file: {workflow_file.name}", err=True)
        
        click.echo("Execute with: fiber functions run-workflow <template_name>")
        
    except Exception as e:
        click.echo(f"Error listing workflow templates: {e}", err=True)


async def _list_agents_async(search: Optional[str], limit: int, verbose: bool, to_instance: str):
    """List agents using direct database access"""
    
    # Route based to_instance parameter  
    if to_instance != 'local':
        click.echo(f"🌐 Remote agent listing for '{to_instance}' not yet implemented.", err=True)
        click.echo("💡 Remote agent listing will be available in a future update.", err=True)
        click.echo("🏠 Use --to-instance local for local database access.", err=True)
        return
    
    config = Config()
    db_provider = None
    
    try:
        db_provider = await _get_database_provider(config, verbose)
        
        # Build query with filters
        query_parts = ["SELECT agent_id, name, description, agent_type, created_at FROM agents"]
        params = []
        
        where_clauses = []
        if search:
            where_clauses.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        if where_clauses:
            query_parts.append("WHERE " + " AND ".join(where_clauses))
        
        query_parts.append("ORDER BY name ASC")
        query_parts.append(f"LIMIT {limit}")
        
        query = " ".join(query_parts)
        
        agents = await db_provider.fetch_all(query, *params)
        
        if not agents:
            click.echo("No agents found")
            return
        
        click.echo(f"\nFound {len(agents)} agent(s):")
        click.echo("-" * 80)
        
        for agent in agents:
            click.echo(f"• {agent['name']} ({agent['agent_type'] or 'unknown'})")
            click.echo(f"  ID: {agent['agent_id']}")
            if agent['description']:
                click.echo(f"  Description: {agent['description']}")
            if verbose:
                click.echo(f"  Created: {agent['created_at']}")
            click.echo()
        
    except Exception as e:
        click.echo(f"Error listing agents: {e}", err=True)
    finally:
        if db_provider:
            await db_provider.disconnect()


async def _show_agent_async(agent_id: str, verbose: bool):
    """Show agent details using direct database access"""
    config = Config()
    db_provider = None
    
    try:
        db_provider = await _get_database_provider(config, verbose)
        
        # Get agent details
        agent = await db_provider.fetch_one(
            "SELECT * FROM agents WHERE agent_id = ? OR name = ?", 
            agent_id, agent_id
        )
        
        if not agent:
            click.echo(f"Agent not found: {agent_id}")
            return
        
        click.echo(f"\nAgent: {agent['name']}")
        click.echo("=" * 50)
        click.echo(f"ID: {agent['agent_id']}")
        click.echo(f"Type: {agent['agent_type'] or 'unknown'}")
        click.echo(f"Created: {agent['created_at']}")
        
        if agent['description']:
            click.echo(f"Description: {agent['description']}")
        
        # Show recent activations
        activations = await db_provider.fetch_all(
            """SELECT activation_id, status, started_at, completed_at 
               FROM activations 
               WHERE agent_id = ? 
               ORDER BY started_at DESC LIMIT 5""",
            agent['agent_id']
        )
        
        if activations:
            click.echo(f"\nRecent Activations (Last 5):")
            click.echo("-" * 30)
            for activation in activations:
                status_icon = "[OK]" if activation['status'] == 'completed' else "[FAIL]" if activation['status'] == 'failed' else "[RUNNING]"
                click.echo(f"{status_icon} {activation['activation_id'][:8]}... - {activation['status']} - {activation['started_at']}")
        
        # Show agent versions if available
        if verbose:
            versions = await db_provider.fetch_all(
                """SELECT version, created_at FROM agent_versions 
                   WHERE agent_id = ? 
                   ORDER BY created_at DESC LIMIT 3""",
                agent['agent_id']
            )
            
            if versions:
                click.echo(f"\nRecent Versions:")
                click.echo("-" * 20)
                for version in versions:
                    click.echo(f"Version {version['version']} - {version['created_at']}")
        
    except Exception as e:
        click.echo(f"Error showing agent: {e}", err=True)
    finally:
        if db_provider:
            await db_provider.disconnect()


async def _activation_history_async(chat_id: Optional[str], agent_id: Optional[str], limit: int, verbose: bool):
    """View activation history for multi-agent conversations"""
    config = Config()
    db_provider = None
    
    try:
        db_provider = await _get_database_provider(config, verbose)
        
        # Build query with filters
        query_parts = ["""
            SELECT a.activation_id, a.agent_id, a.input_data, a.output_data, a.status, 
                   a.started_at, a.completed_at, a.context, ag.name as agent_name
            FROM activations a
            LEFT JOIN agents ag ON a.agent_id = ag.agent_id
        """]
        params = []
        
        where_clauses = []
        if chat_id:
            where_clauses.append("JSON_EXTRACT(a.context, '$.chat_id') = ?")
            params.append(chat_id)
        
        if agent_id:
            where_clauses.append("a.agent_id = ?")
            params.append(agent_id)
        
        if where_clauses:
            query_parts.append("WHERE " + " AND ".join(where_clauses))
        
        query_parts.append("ORDER BY a.started_at ASC")
        query_parts.append(f"LIMIT {limit}")
        
        query = " ".join(query_parts)
        
        activations = await db_provider.fetch_all(query, *params)
        
        if not activations:
            click.echo("No activations found")
            return
        
        click.echo(f"\nFound {len(activations)} activation(s):")
        click.echo("=" * 80)
        
        for i, activation in enumerate(activations):
            click.echo(f"\n{i+1}. Agent: {activation['agent_name'] or activation['agent_id']}")
            click.echo("-" * 60)
            click.echo(f"   Activation ID: {activation['activation_id']}")
            click.echo(f"   Status: {activation['status']}")
            click.echo(f"   Started: {activation['started_at']}")
            if activation['completed_at']:
                click.echo(f"   Completed: {activation['completed_at']}")
            
            # Parse and display context
            if activation['context']:
                try:
                    context_data = json.loads(activation['context'])
                    if context_data.get('chat_id'):
                        click.echo(f"   Chat ID: {context_data['chat_id']}")
                    if context_data.get('session_id'):
                        click.echo(f"   Session ID: {context_data['session_id']}")
                    if verbose and context_data:
                        click.echo(f"   Context: {json.dumps(context_data, indent=4)}")
                except json.JSONDecodeError:
                    if verbose:
                        click.echo(f"   Context: {activation['context']}")
            
            # Show input data
            if activation['input_data'] and verbose:
                try:
                    input_data = json.loads(activation['input_data'])
                    click.echo(f"   Input: {json.dumps(input_data, indent=4)}")
                except json.JSONDecodeError:
                    click.echo(f"   Input: {activation['input_data']}")
            
            # Show output data
            if activation['output_data']:
                try:
                    output_data = json.loads(activation['output_data'])
                    if verbose:
                        click.echo(f"   Output: {json.dumps(output_data, indent=4)}")
                    else:
                        # Show summary for non-verbose mode
                        if isinstance(output_data, dict):
                            if 'status' in output_data:
                                click.echo(f"   Result Status: {output_data['status']}")
                            if 'response' in output_data:
                                response_preview = str(output_data['response'])[:100]
                                if len(str(output_data['response'])) > 100:
                                    response_preview += "..."
                                click.echo(f"   Response: {response_preview}")
                        else:
                            output_preview = str(output_data)[:100]
                            if len(str(output_data)) > 100:
                                output_preview += "..."
                            click.echo(f"   Output: {output_preview}")
                except json.JSONDecodeError:
                    output_preview = str(activation['output_data'])[:100]
                    if len(activation['output_data']) > 100:
                        output_preview += "..."
                    click.echo(f"   Output: {output_preview}")
        
        # Summary
        completed_count = len([a for a in activations if a['status'] == 'completed'])
        failed_count = len([a for a in activations if a['status'] == 'failed'])
        running_count = len([a for a in activations if a['status'] == 'running'])
        
        click.echo(f"\nSummary: {completed_count} completed, {failed_count} failed, {running_count} running")
        
        if chat_id:
            click.echo(f"Filtered by chat_id: {chat_id}")
        if agent_id:
            click.echo(f"Filtered by agent_id: {agent_id}")
        
    except Exception as e:
        click.echo(f"Error retrieving activation history: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc())
    finally:
        if db_provider:
            await db_provider.disconnect()


async def _activate_multi_agent_async(agent_ids: tuple, input_data: Optional[str], context: Optional[str], coordination_mode: str, verbose: bool, to_instance: str):
    """Activate multiple agents with coordination using the activation pattern"""
    
    # Route based on to_instance parameter
    if to_instance != 'local':
        click.echo(f"🌐 Remote multi-agent activation for '{to_instance}' not yet implemented.", err=True)
        click.echo("💡 Remote multi-agent activation will be available in a future update.", err=True)
        click.echo("🏠 Use --to-instance local for local database access.", err=True)
        return
    
    config = Config()
    db_provider = None
    
    try:
        db_provider = await _get_database_provider(config, verbose)
        
        # Import service registry
        from fiberwise_common.services.service_registry import ServiceRegistry
        
        # Create service registry
        activation_service = ServiceRegistry(db_provider)
        
        # Parse input data
        parsed_input = {}
        if input_data:
            try:
                parsed_input = json.loads(input_data)
                if verbose:
                    click.echo(f"Input data: {json.dumps(parsed_input, indent=2)}")
            except json.JSONDecodeError as e:
                click.echo(f"Invalid JSON input data: {e}", err=True)
                return
        
        # Parse context data - use for shared session like chat_id
        parsed_context = {}
        if context:
            try:
                parsed_context = json.loads(context)
                if verbose:
                    click.echo(f"Shared context: {json.dumps(parsed_context, indent=2)}")
            except json.JSONDecodeError as e:
                click.echo(f"Invalid JSON context data: {e}", err=True)
                return
        else:
            # Generate a unique session ID for this multi-agent activation
            import uuid
            parsed_context = {"session_id": str(uuid.uuid4()), "multi_agent_cli": True}
        
        if verbose:
            click.echo(f"Activating {len(agent_ids)} agents in {coordination_mode} mode")
            click.echo(f"Agents: {', '.join(agent_ids)}")
            click.echo(f"Session context: {json.dumps(parsed_context, indent=2)}")
        
        results = []
        current_input = parsed_input.copy()
        
        if coordination_mode == 'parallel':
            # Activate all agents in parallel with same input and context
            import asyncio
            tasks = []
            for agent_id in agent_ids:
                task = activation_service.activate(
                    agent_id=agent_id,
                    input_data={**current_input, **parsed_context},
                    version='latest',
                    verbose=verbose
                )
                tasks.append(task)
            
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(parallel_results):
                if isinstance(result, Exception):
                    click.echo(f"Agent {agent_ids[i]} activation failed: {result}", err=True)
                    results.append({"status": "error", "agent_id": agent_ids[i], "error": str(result)})
                else:
                    results.append({"agent_id": agent_ids[i], **result})
                    
        elif coordination_mode == 'chain':
            # Activate agents in sequence, chaining output to input
            for agent_id in agent_ids:
                if verbose:
                    click.echo(f"\n--- Activating {agent_id} ---")
                
                result = await activation_service.activate(
                    agent_id=agent_id,
                    input_data={**current_input, **parsed_context},
                    version='latest',
                    verbose=verbose
                )
                
                if result and result.get('status') == 'completed':
                    results.append({"agent_id": agent_id, **result})
                    
                    # Use execution result as input for next agent
                    if result.get('execution_result'):
                        current_input = result['execution_result']
                        if verbose:
                            click.echo(f"Chaining output to next agent: {json.dumps(current_input, indent=2)}")
                else:
                    click.echo(f"Agent {agent_id} activation failed, breaking chain", err=True)
                    break
                    
        elif coordination_mode == 'conversation':
            # Conversation mode - like activation-chat, each agent responds to the conversation
            # Use a chat_id context and build up a conversation history
            chat_id = parsed_context.get('chat_id', parsed_context.get('session_id', str(uuid.uuid4())))
            conversation_context = {**parsed_context, "chat_id": chat_id, "role": "multi_agent_conversation"}
            
            if verbose:
                click.echo(f"Starting multi-agent conversation with chat_id: {chat_id}")
            
            for i, agent_id in enumerate(agent_ids):
                if verbose:
                    click.echo(f"\n--- Agent {i+1}: {agent_id} joining conversation ---")
                
                # In conversation mode, each agent gets the original input plus conversation context
                conversation_input = {
                    **current_input,
                    "conversation_turn": i + 1,
                    "previous_agents": list(agent_ids[:i]) if i > 0 else [],
                    "remaining_agents": list(agent_ids[i+1:]) if i < len(agent_ids) - 1 else []
                }
                
                result = await activation_service.activate(
                    agent_id=agent_id,
                    input_data=conversation_input,
                    version='latest',
                    verbose=verbose
                )
                
                if result and result.get('status') == 'completed':
                    results.append({"agent_id": agent_id, "turn": i + 1, **result})
                    if verbose:
                        click.echo(f"Agent {agent_id} completed turn {i + 1}")
                else:
                    click.echo(f"Agent {agent_id} failed in conversation", err=True)
                    results.append({"status": "error", "agent_id": agent_id, "turn": i + 1})
                    
        else:  # sequential mode
            # Activate agents one after another with same input
            for agent_id in agent_ids:
                if verbose:
                    click.echo(f"\n--- Activating {agent_id} ---")
                
                result = await activation_service.activate(
                    agent_id=agent_id,
                    input_data={**current_input, **parsed_context},
                    version='latest',
                    verbose=verbose
                )
                
                if result and result.get('status') == 'completed':
                    results.append({"agent_id": agent_id, **result})
                else:
                    click.echo(f"Agent {agent_id} activation failed", err=True)
                    results.append({"status": "error", "agent_id": agent_id})
        
        # Display results
        click.echo(f"\n[SUCCESS] Multi-agent activation completed!")
        click.echo("=" * 70)
        
        for i, result in enumerate(results):
            agent_name = result.get('agent', {}).get('name', result.get('agent_id', 'unknown'))
            turn_info = f" (Turn {result.get('turn')})" if 'turn' in result else ""
            click.echo(f"\nAgent {i+1}: {agent_name}{turn_info}")
            click.echo("-" * 50)
            
            if verbose:
                if result.get('agent'):
                    click.echo(f"Agent ID: {result['agent'].get('agent_id')}")
                version_str = result.get('version', 'unknown')
                if isinstance(version_str, dict):
                    version_str = version_str.get('version', 'unknown')
                click.echo(f"Version: {version_str}")
                click.echo(f"Status: {result.get('status', 'unknown')}")
            
            if result.get('execution_result'):
                click.echo("Execution Result:")
                try:
                    if isinstance(result['execution_result'], dict):
                        click.echo(json.dumps(result['execution_result'], indent=2))
                    else:
                        click.echo(str(result['execution_result']))
                except:
                    click.echo(str(result['execution_result']))
            
            if result.get('error'):
                click.echo(f"Error: {result['error']}", err=True)
        
        # Summary statistics
        successful = len([r for r in results if r.get('status') == 'completed'])
        failed = len(results) - successful
        
        click.echo(f"\nMulti-Agent Summary: {successful} successful, {failed} failed out of {len(results)} total")
        
        if coordination_mode == 'conversation' and 'chat_id' in parsed_context:
            click.echo(f"Conversation ID: {parsed_context['chat_id']}")
            click.echo("Use this chat_id to continue the conversation or review activation history")
        
    except Exception as e:
        click.echo(f"Error in multi-agent activation: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc())
    finally:
        if db_provider:
            await db_provider.disconnect()


async def _pipeline_status_async(execution_id: str, verbose: bool):
    """Check pipeline execution status using direct database access"""
    config = Config()
    db_provider = None
    
    try:
        db_provider = await _get_database_provider(config, verbose)
        
        # Get execution details
        execution = await db_provider.fetch_one(
            """SELECT pe.*, ap.name as pipeline_name
               FROM pipeline_executions pe
               JOIN agent_pipelines ap ON pe.pipeline_id = ap.pipeline_id
               WHERE pe.execution_id = ?""",
            execution_id
        )
        
        if not execution:
            click.echo(f"Pipeline execution not found: {execution_id}")
            return
        
        click.echo(f"\nPipeline Execution Status")
        click.echo("=" * 40)
        click.echo(f"Execution ID: {execution['execution_id']}")
        click.echo(f"Pipeline: {execution['pipeline_name']}")
        click.echo(f"Status: {execution['status']}")
        click.echo(f"Started: {execution['started_at']}")
        
        if execution['completed_at']:
            click.echo(f"Completed: {execution['completed_at']}")
        
        if execution['duration_ms']:
            click.echo(f"Duration: {execution['duration_ms']} ms")
        
        if execution['error']:
            click.echo(f"Error: {execution['error']}")
        
        if verbose:
            if execution['input_data']:
                try:
                    input_data = json.loads(execution['input_data'])
                    click.echo(f"\nInput Data:")
                    click.echo(json.dumps(input_data, indent=2))
                except json.JSONDecodeError:
                    click.echo(f"Input Data: {execution['input_data']}")
            
            if execution['output_data'] and execution['output_data'] != '{}':
                try:
                    output_data = json.loads(execution['output_data'])
                    click.echo(f"\nOutput Data:")
                    click.echo(json.dumps(output_data, indent=2))
                except json.JSONDecodeError:
                    click.echo(f"Output Data: {execution['output_data']}")
            
            if execution['node_results'] and execution['node_results'] != '{}':
                try:
                    node_results = json.loads(execution['node_results'])
                    click.echo(f"\nNode Results:")
                    click.echo(json.dumps(node_results, indent=2))
                except json.JSONDecodeError:
                    click.echo(f"Node Results: {execution['node_results']}")
        
    except Exception as e:
        click.echo(f"Error checking pipeline status: {e}", err=True)
    finally:
        if db_provider:
            await db_provider.disconnect()


if __name__ == '__main__':
    functions()