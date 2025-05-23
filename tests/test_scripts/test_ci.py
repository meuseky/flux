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

import pytest
from scripts.ci import test_workflow

def test_test_workflow_dryrun():
    """Test the test_workflow function in dry-run mode."""
    result = test_workflow("pull-request.yml", "test", "pull_request", dryrun=True)
    assert result is True

def test_test_workflow_invalid_event():
    """Test test_workflow with an invalid event."""
    with pytest.raises(ValueError, match="Invalid event"):
        test_workflow("pull-request.yml", "test", "invalid_event")
