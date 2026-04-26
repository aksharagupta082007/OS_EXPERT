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

from pipeline.episode_generator import EpisodeGenerator
from reward.safety_oracle import check_safety
from reward.aggregator import breadcrumb_check, calculate_reward
import reward.grader as grader
import random


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
        self._episode_generator = EpisodeGenerator()
        self._current_hidden_state = {}

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
        
        task_id = kwargs.get("task_id", random.randint(1, 15))
        
        # Set task_id on world state so snapshot includes task description
        self._world_state.set_task_id(task_id)
        
        # Refresh the sandbox from Gold Rootfs
        snapshot = self._world_state.reset()

        if seed is None:
            seed = random.randint(0, 1000000)
        
        # Inject deterministic broken state
        from env.sandbox_config import SANDBOX_ROOT
        self._current_hidden_state = self._episode_generator.generate_episode(task_id, seed, SANDBOX_ROOT)

        # Wire hidden_state into router so proc.kill can record agent-kill markers
        self._router.hidden_state = self._current_hidden_state

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

        raw_command = str(action.model_dump())
        
        # 1. Safety Check (Pre-execution)
        is_safe, penalty, reason = check_safety(
            raw_command,
            self._current_hidden_state.get("honeypots", []),
            hidden_state=self._current_hidden_state,
            tool_name=action.tool,
            tool_args=action.params,
        )
        if not is_safe:
            self._current_hidden_state["penalty_risk"] = -penalty
            return SovereignObservation(
                tool_result=ToolResult(status="blocked", stdout=reason, exit_code=1),
                system_snapshot={},
                tool_name=action.tool,
                done=True,
                reward=calculate_reward(self._current_hidden_state, self._state.step_count, 0.0),
                info={"safety_violation": reason}
            )
            
        # 2. Breadcrumbs Check
        breadcrumb_check(self._current_hidden_state, action.tool, raw_command)

        # Dispatch through the action router
        observation = self._router.dispatch(action)

        # Apply transform if configured
        observation = self._apply_transform(observation)
        
        # 3. Grade Outcome
        task_id = self._current_hidden_state.get("task_id", 1)
        grader_func = getattr(grader, f"grade_task_{task_id:02d}", None)
        
        outcome_score = 0.0
        if grader_func:
            outcome_score = grader_func(self._current_hidden_state)
            
        done = False
        if outcome_score == 5.0 or self._state.step_count >= 15:
            done = True
            
        # 4. Final Reward Calculation
        observation.reward = calculate_reward(self._current_hidden_state, self._state.step_count, outcome_score)
        observation.done = done

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
