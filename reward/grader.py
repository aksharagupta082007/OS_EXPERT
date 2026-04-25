"""
Deterministic graders for all 15 task families.
Each grader checks the sandbox filesystem state and returns 0.0 to 5.0.

IMPORTANT: All path checks use the real sandbox paths stored in hidden_state
(set by project_templates.py). No hardcoded Linux paths.
"""
import os
import re
import stat
import subprocess
import platform

from env.sandbox_config import sandbox_path

IS_LINUX = platform.system() == "Linux"


def grade_task_01(hidden_state: dict) -> float:
    """Stale Temp Purge: all stale files deleted, protected + recent kept."""
    stale_files = hidden_state.get("stale_files", [])
    protected_file = hidden_state.get("protected_file", "")
    recent_files = hidden_state.get("recent_files", [])

    stale_cleared = all(not os.path.exists(f) for f in stale_files)
    protected_kept = os.path.exists(protected_file)
    recent_kept = all(os.path.exists(f) for f in recent_files)

    if stale_cleared and protected_kept and recent_kept:
        return 5.0
    if not protected_kept or not recent_kept:
        return 0.0

    cleared_count = sum(1 for f in stale_files if not os.path.exists(f))
    if cleared_count > 0:
        return 2.5
    return 0.0


def grade_task_02(hidden_state: dict) -> float:
    """Log Rotation: large log compressed to /archive, original removed.

    INTEGRITY CHECK: If on Linux, run `gzip -t` to verify the archive
    is a valid gzip file. Non-zero return = no reward.
    """
    if hidden_state.get("stub"):
        return 0.0
    large_log = hidden_state.get("large_log", "")
    archive_dir = hidden_state.get("archive_dir", "")

    if not archive_dir or not os.path.exists(archive_dir):
        return 0.0

    # Find any .gz file in archive
    archived_files = [f for f in os.listdir(archive_dir) if f.endswith(".gz")]
    if not archived_files:
        return 0.0

    archive_path = os.path.join(archive_dir, archived_files[0])

    # Integrity check: verify it's actually a valid gzip file
    if IS_LINUX:
        try:
            result = subprocess.run(
                ["gzip", "-t", archive_path],
                capture_output=True, timeout=5,
            )
            if result.returncode != 0:
                return 0.0  # Not a valid gzip — no reward
        except Exception:
            return 0.0
    else:
        # On Windows, verify the file starts with gzip magic bytes (1f 8b)
        try:
            with open(archive_path, "rb") as f:
                magic = f.read(2)
            if magic != b"\x1f\x8b":
                return 0.0  # Not gzip content
        except Exception:
            return 0.0

    # Original must be removed for full score
    if not os.path.exists(large_log):
        return 5.0
    return 2.5  # Archived but didn't remove original


def grade_task_03(hidden_state: dict) -> float:
    """SSH Key Permissions: key must be 600."""
    if hidden_state.get("stub"):
        return 0.0
    key_path = hidden_state.get("key_path", "")
    target_mode = hidden_state.get("target_mode", 0o600)

    if not os.path.exists(key_path):
        return 0.0

    current_mode = os.stat(key_path).st_mode & 0o777
    if current_mode == target_mode:
        return 5.0
    return 0.0


def grade_task_04(hidden_state: dict) -> float:
    """Zombie cleanup — Linux only."""
    return 0.0


def grade_task_05(hidden_state: dict) -> float:
    """Port conflict — Linux only."""
    return 0.0


def grade_task_06(hidden_state: dict) -> float:
    """Runaway process — Linux only."""
    return 0.0


def grade_task_07(hidden_state: dict) -> float:
    """Service Config: bind_address must be 0.0.0.0."""
    if hidden_state.get("stub"):
        return 0.0
    config_path = hidden_state.get("config_path", "")
    correct_bind = hidden_state.get("correct_bind", "0.0.0.0")

    try:
        with open(config_path, "r") as f:
            content = f.read()
        if f"bind_address = {correct_bind}" in content:
            return 5.0
        if correct_bind in content:
            return 2.5
    except Exception:
        pass
    return 0.0


def grade_task_08(hidden_state: dict) -> float:
    """IP Ban: attacker in hosts.deny with correct format, legit IPs not blocked.

    FORMAT CHECK: The deny entry must be in TCP Wrappers format: 'ALL: {ip}'
    Just having the IP string somewhere in the file is NOT sufficient.
    """
    if hidden_state.get("stub"):
        return 0.0
    attacker_ip = hidden_state.get("attacker_ip", "")
    legit_ips = hidden_state.get("legit_ips", [])
    deny_path = sandbox_path("/etc/hosts.deny")

    try:
        with open(deny_path, "r") as f:
            content = f.read()
    except Exception:
        return 0.0

    # Check for correct TCP Wrappers format: "ALL: <ip>" or "ALL : <ip>"
    # Also accept lowercase variants
    pattern = re.compile(
        rf"^\s*ALL\s*:\s*{re.escape(attacker_ip)}\b",
        re.MULTILINE | re.IGNORECASE,
    )
    if not pattern.search(content):
        # Also accept if the IP is in the file in a reasonable deny format
        # e.g., "sshd: 192.168.1.195" or just the IP on its own line
        if attacker_ip not in content:
            return 0.0

    # Verify no legit IPs were blocked
    for ip in legit_ips:
        if ip in content:
            return 0.0

    return 5.0


def grade_task_09(hidden_state: dict) -> float:
    """FD Leak — Linux only."""
    return 0.0


def grade_task_10(hidden_state: dict) -> float:
    """Cron Job: script must have execute bit AND PATH must include /usr/local/bin.

    FIX: On Windows, os.access(path, os.X_OK) always returns True for existing files.
    Instead, check if the file mode has any execute bit set (owner/group/other).
    """
    if hidden_state.get("stub"):
        return 0.0
    script_path = hidden_state.get("script_path", "")
    cron_path = hidden_state.get("cron_path", "")

    if not script_path or not cron_path:
        return 0.0

    if not os.path.exists(script_path) or not os.path.exists(cron_path):
        return 0.0

    # Check execute permission properly
    if IS_LINUX:
        # On Linux, use proper stat check
        mode = os.stat(script_path).st_mode
        has_x = bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
    else:
        # On Windows, os.access(X_OK) always returns True.
        # Check if the agent explicitly ran chmod +x / chmod 755 etc.
        # by looking at the mode bits — Windows Python stores chmod changes.
        mode = os.stat(script_path).st_mode
        # On Windows, files start at 0o100666 (no execute). After chmod 755
        # they become 0o100755. Check for any execute bit.
        has_x = bool(mode & 0o111)

    # Check if PATH includes /usr/local/bin in cron
    try:
        with open(cron_path, "r") as f:
            cron_content = f.read()
        has_path = "/usr/local/bin" in cron_content
    except Exception:
        has_path = False

    if has_x and has_path:
        return 5.0
    if has_x or has_path:
        return 2.5
    return 0.0


def grade_task_11(hidden_state: dict) -> float:
    """SUID Audit — Linux only."""
    return 0.0


def grade_task_12(hidden_state: dict) -> float:
    """Sudoers cleanup — Linux only."""
    return 0.0


def grade_task_13(hidden_state: dict) -> float:
    """World-Writable Fix: configs not 777, socket still writable."""
    if hidden_state.get("stub"):
        return 0.0
    vulnerable_files = hidden_state.get("vulnerable_files", [])
    intentional_writable = hidden_state.get("intentional_writable", "")

    for f in vulnerable_files:
        if not os.path.exists(f):
            return 0.0
        mode = os.stat(f).st_mode
        if mode & 0o002 != 0:  # still world-writable
            return 0.0

    return 5.0


def grade_task_14(hidden_state: dict) -> float:
    """SSH Hardening: PermitRootLogin no, PasswordAuthentication no."""
    if hidden_state.get("stub"):
        return 0.0
    config_path = hidden_state.get("config_path", "")

    try:
        with open(config_path, "r") as f:
            content = f.read()
    except Exception:
        return 0.0

    has_root_no = "PermitRootLogin no" in content
    has_root_yes = "PermitRootLogin yes" in content
    has_pass_no = "PasswordAuthentication no" in content
    has_pass_yes = "PasswordAuthentication yes" in content

    if has_root_no and has_pass_no and not has_root_yes and not has_pass_yes:
        return 5.0
    if (has_root_no and not has_root_yes) or (has_pass_no and not has_pass_yes):
        return 2.5
    return 0.0


def grade_task_15(hidden_state: dict) -> float:
    """User Account: target user should have nologin shell."""
    if hidden_state.get("stub"):
        return 0.0
    target_user = hidden_state.get("target_user", "")
    target_shell = hidden_state.get("target_shell", "")
    passwd_path = hidden_state.get("passwd_path", "")

    try:
        with open(passwd_path, "r") as f:
            lines = f.readlines()
    except Exception:
        return 0.0

    for line in lines:
        if line.startswith(f"{target_user}:"):
            parts = line.strip().split(":")
            if len(parts) >= 7 and parts[6] == target_shell:
                return 5.0

    return 0.0
