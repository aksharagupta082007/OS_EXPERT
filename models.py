# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the OS Expert Environment.

Defines SovereignAction (a discriminated union of 35+ typed tool calls)
and SovereignObservation (structured multi-modal output) for the
OS_EXPERT_ENV reinforcement-learning sandbox.
"""

from typing import Any, Dict, List, Literal, Optional, Union

from openenv.core.env_server.types import Action, Observation
from pydantic import BaseModel, Field


# =============================================================================
# Tool Result — every tool returns this structure
# =============================================================================


class ToolResult(BaseModel):
    """Structured result returned by every tool execution."""

    status: Literal["success", "error", "timeout", "blocked"] = Field(
        ..., description="Execution status"
    )
    stdout: str = Field(default="", description="Standard output from command")
    stderr: str = Field(default="", description="Standard error from command")
    exit_code: int = Field(default=-1, description="Process exit code")
    state_delta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key state changes caused by the action (e.g., files modified)",
    )


# =============================================================================
# Filesystem Tool Parameters (8 tools)
# =============================================================================


class FsListParams(BaseModel):
    """Parameters for fs.list — list directory contents (metadata only)."""

    path: str = Field(default="/", description="Directory path to list")
    recursive: bool = Field(default=False, description="Recurse into subdirectories")
    max_depth: int = Field(default=1, ge=1, le=10, description="Max recursion depth")


class FsReadParams(BaseModel):
    """Parameters for fs.read — read file contents."""

    path: str = Field(..., description="File path to read")
    offset: int = Field(default=0, ge=0, description="Byte offset to start reading")
    limit: int = Field(
        default=4096, ge=1, le=65536, description="Max bytes to read"
    )


class FsWriteParams(BaseModel):
    """Parameters for fs.write — write content to a file."""

    path: str = Field(..., description="File path to write")
    content: str = Field(..., description="Content to write")
    append: bool = Field(default=False, description="Append instead of overwrite")


class FsSearchParams(BaseModel):
    """Parameters for fs.search — search for files or content."""

    path: str = Field(default="/", description="Root path to search from")
    name: Optional[str] = Field(default=None, description="Filename glob pattern")
    content: Optional[str] = Field(
        default=None, description="Grep pattern to search inside files"
    )
    max_results: int = Field(default=50, ge=1, le=200, description="Max results")


class FsStatParams(BaseModel):
    """Parameters for fs.stat — get detailed file metadata."""

    path: str = Field(..., description="File or directory path")


class FsHashParams(BaseModel):
    """Parameters for fs.hash — compute SHA-256 checksum."""

    path: str = Field(..., description="File path to hash")


class FsChmodParams(BaseModel):
    """Parameters for fs.chmod — change file permissions."""

    path: str = Field(..., description="File path")
    mode: str = Field(
        ..., description="Permission mode (e.g., '644', '755', 'u+x')"
    )
    recursive: bool = Field(default=False, description="Apply recursively")


class FsChownParams(BaseModel):
    """Parameters for fs.chown — change file ownership."""

    path: str = Field(..., description="File path")
    owner: str = Field(..., description="New owner (user:group or user)")
    recursive: bool = Field(default=False, description="Apply recursively")


# =============================================================================
# Process / System Tool Parameters (8 tools)
# =============================================================================


class ProcListParams(BaseModel):
    """Parameters for proc.list — list running processes."""

    filter: Optional[str] = Field(
        default=None, description="Filter by process name pattern"
    )
    sort_by: Literal["cpu", "mem", "pid", "name"] = Field(
        default="pid", description="Sort criterion"
    )


class ProcKillParams(BaseModel):
    """Parameters for proc.kill — send signal to a process."""

    pid: int = Field(..., ge=1, description="Process ID to signal")
    signal: int = Field(default=15, ge=1, le=64, description="Signal number (default SIGTERM)")


class SvcStatusParams(BaseModel):
    """Parameters for svc.status — check service status."""

    service: str = Field(..., description="Service name (e.g., 'nginx', 'ssh')")


class SvcRestartParams(BaseModel):
    """Parameters for svc.restart — restart a system service."""

    service: str = Field(..., description="Service name to restart")


class PkgInstallParams(BaseModel):
    """Parameters for pkg.install — install a system package."""

    package: str = Field(..., description="Package name to install")
    version: Optional[str] = Field(default=None, description="Specific version")


class SysLogsParams(BaseModel):
    """Parameters for sys.logs — read system log entries."""

    source: str = Field(
        default="syslog",
        description="Log source (syslog, auth, kern, dmesg, nginx, etc.)",
    )
    lines: int = Field(default=50, ge=1, le=500, description="Number of lines to read")
    pattern: Optional[str] = Field(
        default=None, description="Grep filter pattern"
    )


class SysDiskUsageParams(BaseModel):
    """Parameters for sys.disk_usage — check disk usage."""

    path: str = Field(default="/", description="Path to check")


class SysUptimeParams(BaseModel):
    """Parameters for sys.uptime — get system uptime."""

    pass


# =============================================================================
# Network Tool Parameters (7 tools)
# =============================================================================


class NetPortsParams(BaseModel):
    """Parameters for net.ports — list listening ports."""

    protocol: Literal["tcp", "udp", "all"] = Field(
        default="all", description="Protocol filter"
    )


class NetPingParams(BaseModel):
    """Parameters for net.ping — ping a host."""

    host: str = Field(..., description="Host to ping")
    count: int = Field(default=3, ge=1, le=10, description="Number of pings")


class NetCurlParams(BaseModel):
    """Parameters for net.curl — make an HTTP request."""

    url: str = Field(..., description="URL to request")
    method: Literal["GET", "POST", "PUT", "DELETE", "HEAD"] = Field(
        default="GET", description="HTTP method"
    )
    headers: Dict[str, str] = Field(
        default_factory=dict, description="Request headers"
    )
    body: Optional[str] = Field(default=None, description="Request body")
    timeout: int = Field(default=10, ge=1, le=30, description="Timeout in seconds")


class NetDnsLookupParams(BaseModel):
    """Parameters for net.dns_lookup — resolve DNS records."""

    domain: str = Field(..., description="Domain to look up")
    record_type: Literal["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"] = Field(
        default="A", description="DNS record type"
    )


class NetFirewallRuleParams(BaseModel):
    """Parameters for net.firewall_rule — manage iptables rules."""

    action: Literal["list", "add", "delete"] = Field(
        ..., description="Firewall action"
    )
    chain: Literal["INPUT", "OUTPUT", "FORWARD"] = Field(
        default="INPUT", description="Chain"
    )
    protocol: Optional[Literal["tcp", "udp", "icmp"]] = Field(
        default=None, description="Protocol"
    )
    port: Optional[int] = Field(default=None, ge=1, le=65535, description="Port number")
    target: Literal["ACCEPT", "DROP", "REJECT", "LOG"] = Field(
        default="ACCEPT", description="Rule target"
    )
    source: Optional[str] = Field(default=None, description="Source IP/CIDR")


class NetTraceParams(BaseModel):
    """Parameters for net.trace — traceroute to a host."""

    host: str = Field(..., description="Destination host")
    max_hops: int = Field(default=15, ge=1, le=30, description="Maximum hops")


class NetSshCheckParams(BaseModel):
    """Parameters for net.ssh_check — check SSH configuration."""

    config_path: str = Field(
        default="/etc/ssh/sshd_config", description="SSH config file path"
    )


# =============================================================================
# Security / Audit Tool Parameters (6 tools)
# =============================================================================


class AuditUserHistoryParams(BaseModel):
    """Parameters for audit.user_history — view user command history."""

    user: str = Field(default="root", description="Username")
    lines: int = Field(default=50, ge=1, le=500, description="Number of history lines")


class SecScanVulnParams(BaseModel):
    """Parameters for sec.scan_vuln — scan for known vulnerabilities."""

    target: str = Field(
        default="localhost", description="Target to scan (host or path)"
    )
    scan_type: Literal["quick", "full", "web"] = Field(
        default="quick", description="Scan depth"
    )


class SecCheckSuidParams(BaseModel):
    """Parameters for sec.check_suid — find SUID/SGID binaries."""

    path: str = Field(default="/", description="Root path to scan")


class SecIntegrityCheckParams(BaseModel):
    """Parameters for sec.integrity_check — verify package file integrity."""

    package: Optional[str] = Field(
        default=None, description="Specific package (or None for all)"
    )


class AuditAuthLogsParams(BaseModel):
    """Parameters for audit.auth_logs — review authentication logs."""

    lines: int = Field(default=50, ge=1, le=500, description="Number of log lines")
    pattern: Optional[str] = Field(
        default=None, description="Filter pattern (e.g., 'Failed')"
    )


class SecDryRunParams(BaseModel):
    """Parameters for sec.dry_run — simulate a command without executing."""

    command: str = Field(..., description="Command to simulate")


# =============================================================================
# Workspace / Meta Tool Parameters (6 tools)
# =============================================================================


class WsStatusParams(BaseModel):
    """Parameters for ws.status — get overall workspace status."""

    pass


class WsThinkStepParams(BaseModel):
    """Parameters for ws.think_step — agent scratchpad / chain-of-thought."""

    thought: str = Field(..., description="The agent's reasoning step")


class TaskSubmitParams(BaseModel):
    """Parameters for task.submit — signal task completion."""

    summary: str = Field(..., description="Summary of actions taken")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Agent's confidence in solution"
    )


class MemoDraftParams(BaseModel):
    """Parameters for memo.draft — write to a persistent scratch notepad."""

    content: str = Field(..., description="Memo content")
    tag: str = Field(default="general", description="Categorization tag")


class EnvGetVarParams(BaseModel):
    """Parameters for env.get_var — read an environment variable."""

    name: str = Field(..., description="Environment variable name")


class FsCompareVersionsParams(BaseModel):
    """Parameters for fs.compare_versions — diff current file vs gold image."""

    path: str = Field(..., description="File path to compare")


# =============================================================================
# SovereignAction — Discriminated union of all tool calls
# =============================================================================

# Union of all tool parameter types
ToolParams = Union[
    # Filesystem (8)
    FsListParams,
    FsReadParams,
    FsWriteParams,
    FsSearchParams,
    FsStatParams,
    FsHashParams,
    FsChmodParams,
    FsChownParams,
    # Process/System (8)
    ProcListParams,
    ProcKillParams,
    SvcStatusParams,
    SvcRestartParams,
    PkgInstallParams,
    SysLogsParams,
    SysDiskUsageParams,
    SysUptimeParams,
    # Network (7)
    NetPortsParams,
    NetPingParams,
    NetCurlParams,
    NetDnsLookupParams,
    NetFirewallRuleParams,
    NetTraceParams,
    NetSshCheckParams,
    # Security/Audit (6)
    AuditUserHistoryParams,
    SecScanVulnParams,
    SecCheckSuidParams,
    SecIntegrityCheckParams,
    AuditAuthLogsParams,
    SecDryRunParams,
    # Workspace/Meta (6)
    WsStatusParams,
    WsThinkStepParams,
    TaskSubmitParams,
    MemoDraftParams,
    EnvGetVarParams,
    FsCompareVersionsParams,
]

# Canonical tool name list (used for validation)
TOOL_NAMES: List[str] = [
    # Filesystem
    "fs.list", "fs.read", "fs.write", "fs.search",
    "fs.stat", "fs.hash", "fs.chmod", "fs.chown",
    # Process/System
    "proc.list", "proc.kill", "svc.status", "svc.restart",
    "pkg.install", "sys.logs", "sys.disk_usage", "sys.uptime",
    # Network
    "net.ports", "net.ping", "net.curl", "net.dns_lookup",
    "net.firewall_rule", "net.trace", "net.ssh_check",
    # Security/Audit
    "audit.user_history", "sec.scan_vuln", "sec.check_suid",
    "sec.integrity_check", "audit.auth_logs", "sec.dry_run",
    # Workspace/Meta
    "ws.status", "ws.think_step", "task.submit",
    "memo.draft", "env.get_var", "fs.compare_versions",
]

# Map tool names -> parameter model classes
TOOL_PARAM_MAP: Dict[str, type] = {
    # Filesystem
    "fs.list": FsListParams,
    "fs.read": FsReadParams,
    "fs.write": FsWriteParams,
    "fs.search": FsSearchParams,
    "fs.stat": FsStatParams,
    "fs.hash": FsHashParams,
    "fs.chmod": FsChmodParams,
    "fs.chown": FsChownParams,
    # Process/System
    "proc.list": ProcListParams,
    "proc.kill": ProcKillParams,
    "svc.status": SvcStatusParams,
    "svc.restart": SvcRestartParams,
    "pkg.install": PkgInstallParams,
    "sys.logs": SysLogsParams,
    "sys.disk_usage": SysDiskUsageParams,
    "sys.uptime": SysUptimeParams,
    # Network
    "net.ports": NetPortsParams,
    "net.ping": NetPingParams,
    "net.curl": NetCurlParams,
    "net.dns_lookup": NetDnsLookupParams,
    "net.firewall_rule": NetFirewallRuleParams,
    "net.trace": NetTraceParams,
    "net.ssh_check": NetSshCheckParams,
    # Security/Audit
    "audit.user_history": AuditUserHistoryParams,
    "sec.scan_vuln": SecScanVulnParams,
    "sec.check_suid": SecCheckSuidParams,
    "sec.integrity_check": SecIntegrityCheckParams,
    "audit.auth_logs": AuditAuthLogsParams,
    "sec.dry_run": SecDryRunParams,
    # Workspace/Meta
    "ws.status": WsStatusParams,
    "ws.think_step": WsThinkStepParams,
    "task.submit": TaskSubmitParams,
    "memo.draft": MemoDraftParams,
    "env.get_var": EnvGetVarParams,
    "fs.compare_versions": FsCompareVersionsParams,
}


class SovereignAction(Action):
    """A typed tool call sent by the RL agent.

    The agent selects a tool by name and provides typed parameters.
    The action router validates the tool name against TOOL_NAMES and
    deserializes params using the corresponding Pydantic model.
    """

    tool: str = Field(
        ...,
        description="Tool name (e.g., 'fs.read', 'proc.list', 'net.curl')",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool parameters (validated against the tool's param model)",
    )


class SovereignObservation(Observation):
    """Structured observation returned after every tool execution.

    Combines the tool result with an optional system snapshot and
    safety violation information.
    """

    tool_result: ToolResult = Field(
        default_factory=lambda: ToolResult(status="success"),
        description="Result of the tool execution",
    )
    system_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        description="Partial system state snapshot (uptime, load, etc.)",
    )
    safety_violation: Optional[str] = Field(
        default=None,
        description="Description of safety rule violation, if any",
    )
    tool_name: str = Field(
        default="",
        description="Name of the tool that was executed",
    )
    info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Hidden metadata for evaluation/debugging (ignored by agent)",
    )
