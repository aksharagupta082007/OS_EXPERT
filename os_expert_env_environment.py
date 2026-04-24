# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
OS Expert Environment — OpenEnv Environment implementation.

A high-fidelity, sandboxed Linux environment for training RL agents
in secure system administration. Uses a chroot-based filesystem jail
with a Gold Rootfs snapshot for fast resets.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from .models import SovereignAction, SovereignObservation, ToolResult
except ImportError:
    from models import SovereignAction, SovereignObservation, ToolResult

try:
    from .env.world_state import WorldState
    from .env.action_router import ActionRouter
except ImportError:
    from env.world_state import WorldState
    from env.action_router import ActionRouter

logger = logging.getLogger(__name__)


class OsExpertEnvironment(Environment):
    """OpenEnv Environment for OS administration RL training.

    Lifecycle:
        1. ``reset()`` — refreshes sandbox from Gold Rootfs, returns initial obs
        2. ``step(action)`` — dispatches a tool call, returns observation
        3. ``close()`` — cleans up the sandbox directory

    The reset copies the Gold Rootfs into /tmp/active_sandbox and
    commands are executed inside it via chroot.

    Example::

        env = OsExpertEnvironment()
        obs = env.reset()
        obs = env.step(SovereignAction(tool="fs.list", params={"path": "/etc"}))
        obs = env.step(SovereignAction(tool="sys.uptime", params={}))
        env.close()
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self) -> None:
        """Initialize the OS Expert environment."""
        super().__init__()
        self._world_state = WorldState()
        self._router = ActionRouter(self._world_state)
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._reset_count = 0

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> SovereignObservation:
        """Reset the environment by refreshing the sandbox from Gold Rootfs.

        Wipes /tmp/active_sandbox and copies the pristine Gold Rootfs
        snapshot into it.

        Args:
            seed: Unused (deterministic environment).
            episode_id: Optional custom episode identifier.
            **kwargs: Additional reset parameters.

        Returns:
            SovereignObservation with initial system snapshot.
        """
        self._reset_rubric()

        # Refresh the sandbox from Gold Rootfs
        snapshot = self._world_state.reset()

        # Update episode state
        eid = episode_id or self._world_state.episode_id
        self._state = State(episode_id=eid, step_count=0)
        self._reset_count += 1

        logger.info(
            "Environment reset #%d — episode=%s",
            self._reset_count,
            eid[:8],
        )

        return SovereignObservation(
            tool_result=ToolResult(
                status="success",
                stdout="Environment reset complete. Sandbox ready.",
                exit_code=0,
            ),
            system_snapshot=snapshot,
            tool_name="env.reset",
            done=False,
            reward=0.0,
            info={
                "dev_mode": self._router.is_dev_mode,
                "platform": __import__('platform').system(),
            },
        )

    def step(
        self,
        action: SovereignAction,  # type: ignore[override]
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> SovereignObservation:
        """Execute a tool call in the sandbox.

        Args:
            action: SovereignAction with tool name and typed params.
            timeout_s: Optional timeout override.
            **kwargs: Additional step parameters.

        Returns:
            SovereignObservation with tool result and optional snapshot.
        """
        self._state.step_count += 1

        # Dispatch through the action router
        observation = self._router.dispatch(action)

        # Apply transform if configured
        observation = self._apply_transform(observation)

        logger.debug(
            "Step %d — tool=%s status=%s",
            self._state.step_count,
            action.tool,
            observation.tool_result.status,
        )

        return observation

    @property
    def state(self) -> State:
        """Get the current environment state."""
        return self._state

    def close(self) -> None:
        """Clean up the sandbox directory."""
        logger.info("Closing OsExpertEnvironment")
        self._world_state.shutdown()
