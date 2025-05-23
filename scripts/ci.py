# Copyright 2025 Flux Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import subprocess
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def test_workflows():
    """Run all workflow tests.

    Tests the following workflows: pull-request.yml, build-publish.yml, docs.yml.
    Raises:
        subprocess.CalledProcessError: If a workflow test fails.
        FileNotFoundError: If a workflow file is missing.
    """
    workflows = ["pull-request.yml", "build-publish.yml", "docs.yml"]
    for workflow in workflows:
        logging.info(f"Testing workflow: {workflow}")
        try:
            test_workflow(workflow, "test", "pull_request")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logging.error(f"Failed to test workflow {workflow}: {e}")
            sys.exit(1)

def test_workflow(workflow: str, job: str, event: str, dryrun: bool = False) -> bool:
    """Test a specific CI workflow using act.

    Args:
        workflow (str): The workflow file (e.g., "pull-request.yml").
        job (str): The job to run (e.g., "test", "deploy").
        event (str): The GitHub event triggering the workflow (e.g., "push", "pull_request").
        dryrun (bool): If True, perform a dry run without executing the workflow.

    Returns:
        bool: True if the workflow test succeeds, False otherwise.

    Raises:
        FileNotFoundError: If the workflow file or act binary is not found.
        ValueError: If the event or job is invalid.
        subprocess.CalledProcessError: If the workflow execution fails.

    Example:
        >>> test_workflow("pull-request.yml", "test", "pull_request", dryrun=True)
    """
    # Validate inputs
    valid_events = {"push", "pull_request", "release"}
    if event not in valid_events:
        raise ValueError(f"Invalid event: {event}. Must be one of {valid_events}")

    workflow_path = Path(".github/workflows") / workflow
    if not workflow_path.exists():
        raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

    # Check if act is installed
    try:
        subprocess.run(["act", "--version"], check=True, capture_output=True, text=True)
    except FileNotFoundError:
        logging.error("act is not installed. Please install it: https://github.com/nektos/act")
        raise

    # Set up environment variables (mimicking CI)
    env = os.environ.copy()
    env.update({
        "FLUX_DATABASE_URL": "sqlite:///.flux/flux.db",  # For local testing
        "FLUX_CACHE_REDIS_HOST": "localhost",
        "FLUX_EXECUTOR_DISTRIBUTED_CONFIG_RABBITMQ_HOST": "localhost",
    })

    # Build act command
    cmd = [
        "act",
        event,
        "-j", job,
        "-W", str(workflow_path),
    ]
    if dryrun:
        cmd.append("--dryrun")

    # Run the workflow
    logging.info(f"Running command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        logging.info(f"Workflow output:\n{result.stdout}")
        if result.stderr:
            logging.warning(f"Workflow warnings:\n{result.stderr}")
        logging.info(f"Workflow {workflow} (job: {job}, event: {event}) completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Workflow {workflow} (job: {job}, event: {event}) failed")
        logging.error(f"Error output:\n{e.stderr}")
        raise
