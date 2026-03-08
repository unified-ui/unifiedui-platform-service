#!/usr/bin/env python3
"""
Dynamic DevUI Starter Script

This script reads workflow files from a specified directory (e.g., ./workflow-project-1)
and serves them using the Microsoft Agent Framework DevUI (mig serve).

The files are read and executed dynamically, which allows for future scenarios where
workflow files are stored on cloud storage (e.g., Azure Storage Account) and need to
be downloaded and executed at runtime.

Usage:
    python start_dynamic_devui.py
    python start_dynamic_devui.py --workflow-dir ./workflow-project-1
    python start_dynamic_devui.py --port 8090 --no-auto-open
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any


def setup_logging() -> logging.Logger:
    """Configure logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)


def read_workflow_files(workflow_dir: Path, logger: logging.Logger) -> list[Path]:
    """
    Read all Python workflow files from the specified directory.

    Args:
        workflow_dir: Directory containing workflow files
        logger: Logger instance

    Returns:
        List of workflow file paths
    """
    if not workflow_dir.exists():
        logger.error(f"Workflow directory does not exist: {workflow_dir}")
        sys.exit(1)

    if not workflow_dir.is_dir():
        logger.error(f"Workflow path is not a directory: {workflow_dir}")
        sys.exit(1)

    # Find all Python files (excluding __pycache__ and private files)
    workflow_files = [
        f for f in workflow_dir.glob("*.py")
        if not f.name.startswith("_") and f.name != "__init__.py"
    ]

    if not workflow_files:
        logger.warning(f"No workflow files found in: {workflow_dir}")
        return []

    logger.info(f"Found {len(workflow_files)} workflow file(s):")
    for wf in workflow_files:
        logger.info(f"  - {wf.name}")

    return workflow_files


def load_workflow_module(workflow_file: Path, logger: logging.Logger) -> dict[str, Any]:
    """
    Dynamically load a workflow Python file and extract its module contents.

    This reads the file content and executes it to get the workflow objects.
    In the future, this can be adapted to read files from cloud storage.

    Args:
        workflow_file: Path to the workflow Python file
        logger: Logger instance

    Returns:
        Dictionary containing the module's global namespace
    """
    logger.info(f"Loading workflow from: {workflow_file.name}")

    try:
        # Read file content (this is where you could fetch from Azure Storage)
        with open(workflow_file, "r", encoding="utf-8") as f:
            workflow_code = f.read()

        logger.debug(f"Read {len(workflow_code)} characters from {workflow_file.name}")

        # Create a namespace for execution
        module_namespace: dict[str, Any] = {
            "__file__": str(workflow_file),
            "__name__": workflow_file.stem,
        }

        # Execute the workflow code in the namespace
        exec(workflow_code, module_namespace)

        logger.info(f"Successfully loaded workflow: {workflow_file.name}")
        return module_namespace

    except Exception as e:
        logger.error(f"Failed to load workflow {workflow_file.name}: {e}")
        raise


def extract_workflows(module_namespace: dict[str, Any], logger: logging.Logger) -> list[Any]:
    """
    Extract workflow entities from a loaded module.

    Args:
        module_namespace: Module's global namespace
        logger: Logger instance

    Returns:
        List of workflow entities
    """
    from agent_framework import Workflow

    workflows = []

    # Look for workflow objects in the module
    for name, obj in module_namespace.items():
        if isinstance(obj, Workflow):
            workflows.append(obj)
            logger.info(f"  Found workflow entity: {name} ({obj.name})")

    return workflows


def serve_workflows(
    workflows: list[Any],
    port: int,
    auto_open: bool,
    logger: logging.Logger
) -> None:
    """
    Start the DevUI server with the loaded workflows.

    Args:
        workflows: List of workflow entities to serve
        port: Port number for the server
        auto_open: Whether to automatically open the browser
        logger: Logger instance
    """
    if not workflows:
        logger.error("No workflows to serve!")
        sys.exit(1)

    from agent_framework.devui import serve

    logger.info("\n" + "="*60)
    logger.info("Starting Microsoft Agent Framework DevUI")
    logger.info(f"Port: {port}")
    logger.info(f"URL: http://localhost:{port}")
    logger.info(f"Workflows loaded: {len(workflows)}")
    for wf in workflows:
        logger.info(f"  - {wf.name}: {wf.description}")
    logger.info("="*60 + "\n")

    try:
        serve(entities=workflows, port=port, auto_open=auto_open)
    except KeyboardInterrupt:
        logger.info("\nShutting down DevUI server...")
    except Exception as e:
        logger.error(f"Error running DevUI server: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the dynamic DevUI starter."""
    parser = argparse.ArgumentParser(
        description="Dynamically load and serve workflows using Agent Framework DevUI"
    )
    parser.add_argument(
        "--workflow-dir",
        type=str,
        default="./workflow-project-1",
        help="Directory containing workflow files (default: ./workflow-project-1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8090,
        help="Port number for the DevUI server (default: 8090)"
    )
    parser.add_argument(
        "--no-auto-open",
        action="store_true",
        help="Do not automatically open the browser"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Setup logging
    logger = setup_logging()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Dynamic DevUI Starter - Microsoft Agent Framework")

    # Resolve workflow directory
    workflow_dir = Path(args.workflow_dir).resolve()
    logger.info(f"Workflow directory: {workflow_dir}")

    # Read workflow files from directory
    workflow_files = read_workflow_files(workflow_dir, logger)

    if not workflow_files:
        logger.error("No workflow files found. Exiting.")
        sys.exit(1)

    # Load all workflows
    all_workflows = []
    for workflow_file in workflow_files:
        try:
            module_namespace = load_workflow_module(workflow_file, logger)
            workflows = extract_workflows(module_namespace, logger)
            all_workflows.extend(workflows)
        except Exception as e:
            logger.warning(f"Skipping {workflow_file.name} due to error: {e}")
            continue

    # Start the DevUI server
    serve_workflows(
        workflows=all_workflows,
        port=args.port,
        auto_open=not args.no_auto_open,
        logger=logger
    )


if __name__ == "__main__":
    main()
