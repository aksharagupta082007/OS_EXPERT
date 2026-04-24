# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""OS Expert Environment Client."""

from typing import Any, Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import SovereignAction, SovereignObservation, ToolResult


class OsExpertEnv(
    EnvClient[SovereignAction, SovereignObservation, State]
):
    """Client for the OS Expert Environment.

    Maintains a persistent WebSocket connection to the environment server
    for efficient multi-step interactions with lower latency.

    Example::

        with OsExpertEnv(base_url="http://localhost:8000") as client:
            result = client.reset()
            print(result.observation.system_snapshot)

            result = client.step(SovereignAction(
                tool="fs.list",
                params={"path": "/etc"}
            ))
            print(result.observation.tool_result.stdout)
    """

    def _step_payload(self, action: SovereignAction) -> Dict[str, Any]:
        """Convert SovereignAction to JSON payload for step message."""
        return {
            "tool": action.tool,
            "params": action.params,
        }

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[SovereignObservation]:
        """Parse server response into StepResult[SovereignObservation]."""
        obs_data = payload.get("observation", {})

        # Parse the nested ToolResult
        tr_data = obs_data.get("tool_result", {})
        tool_result = ToolResult(
            status=tr_data.get("status", "error"),
            stdout=tr_data.get("stdout", ""),
            stderr=tr_data.get("stderr", ""),
            exit_code=tr_data.get("exit_code", -1),
            state_delta=tr_data.get("state_delta", {}),
        )

        observation = SovereignObservation(
            tool_result=tool_result,
            system_snapshot=obs_data.get("system_snapshot", {}),
            safety_violation=obs_data.get("safety_violation"),
            tool_name=obs_data.get("tool_name", ""),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> State:
        """Parse server response into State object."""
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
