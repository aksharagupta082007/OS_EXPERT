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

def sandbox_path(hidden_state: dict, path: str) -> str:
    root = hidden_state.get("sandbox_root", "")
    return os.path.join(root, path.lstrip('/'))

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
    """Network Service Audit: DNS fixed, weak ciphers removed, firewall allows port."""
    if hidden_state.get("stub"):
        return 0.0
    score = 0.0

    # 1. /etc/hosts has correct IP for service hostname
    hosts = sandbox_path(hidden_state, "/etc/hosts")
    try:
        content = open(hosts).read()
        correct_ip = hidden_state.get("correct_ip", "10.0.0.5")
        hostname = hidden_state.get("service_hostname", "myservice.local")
        if correct_ip in content and hostname in content:
            score += 1.5
    except Exception:
        pass

    # 2. sshd_config has no weak ciphers
    sshd = sandbox_path(hidden_state, "/etc/ssh/sshd_config")
    try:
        content = open(sshd).read()
        weak = hidden_state.get("weak_ciphers", [])
        has_weak = any(c in content for c in weak)
        if not has_weak:
            score += 1.5
    except Exception:
        pass

    # 3. Firewall allows the service port
    fw_path = hidden_state.get("fw_path", "")
    try:
        content = open(fw_path).read()
        port = hidden_state.get("port", 8080)
        if f"--dport {port} -j ACCEPT" in content:
            score += 2.0
    except Exception:
        pass

    return score


def grade_task_03(hidden_state: dict) -> float:
    """SSH Key Permissions: key must be 600, and the key must be at the exact expected path."""
    if hidden_state.get("stub"):
        return 0.0
    key_path = hidden_state.get("key_path", "")
    target_mode = hidden_state.get("target_mode", 0o600)

    if not key_path:
        return 0.0

    # REWARD-HACK GUARD: The grader only checks the specific key file injected
    # by the setup. Chmoding /home or any other directory returns 0.
    if not os.path.isfile(key_path):
        return 0.0

    ssh_dir = os.path.dirname(key_path)
    if ssh_dir and os.path.exists(ssh_dir):
        dir_mode = os.stat(ssh_dir).st_mode
        if (dir_mode & 0o111) == 0:
            hidden_state["task_03_nuked_dir_x"] = True

    if not os.path.exists(key_path):
        return 0.0

    current_mode = os.stat(key_path).st_mode & 0o777
    if current_mode == target_mode:
        return 5.0
    return 0.0


def grade_task_04(hidden_state: dict) -> float:
    """Zombie cleanup — Linux only."""
    target_parent_pid = hidden_state.get("target_parent_pid", "")
    try:
        out = subprocess.check_output(["ps", "-eo", "pid,ppid,stat,command"], text=True)
        for line in out.splitlines()[1:]:
            parts = line.split(maxsplit=3)
            if len(parts) >= 3:
                stat = parts[2]
                ppid = parts[1]
                if 'Z' in stat:
                    if target_parent_pid and ppid == str(target_parent_pid):
                        return 0.0
                    elif not target_parent_pid:
                        return 0.0
        return 5.0
    except Exception:
        return 0.0

def grade_task_05(hidden_state: dict) -> float:
    """Port conflict: agent must explicitly kill the rogue process."""
    target_port = hidden_state.get("target_port", "")
    rogue_pid = hidden_state.get("rogue_pid")
    if not target_port:
        return 0.0

    # Guard: setup never ran (non-Linux), or process was never alive
    if rogue_pid is None:
        return 0.0

    # CRITICAL: Require explicit agent action — prevents false-success from external kills
    if not hidden_state.get("agent_killed_target", False):
        return 0.0

    if IS_LINUX:
        try:
            # Verify port is now actually free
            out = subprocess.check_output(["ss", "-tulpn"], text=True)
            port_str = f":{target_port} "
            port_still_bound = any(
                port_str in line and "LISTEN" in line
                for line in out.splitlines()
            )
            return 0.0 if port_still_bound else 5.0
        except Exception:
            return 0.0
    else:
        # Windows: agent_killed_target + pid in killed_pids.txt
        killed_file = sandbox_path(hidden_state, "/var/run/killed_pids.txt")
        if os.path.exists(killed_file):
            with open(killed_file) as f:
                if str(rogue_pid) in f.read():
                    return 5.0
        return 0.0

def grade_task_06(hidden_state: dict) -> float:
    """Security Incident Response: SUID cleared, user locked, attacker banned."""
    if hidden_state.get("stub"):
        return 0.0
    score = 0.0
    suid_path = hidden_state.get("suid_path", "")
    user = hidden_state.get("compromised_user", "")
    attacker_ip = hidden_state.get("attacker_ip", "")

    # 1. SUID binary removed or SUID bit cleared
    if suid_path:
        if not os.path.exists(suid_path):
            score += 2.0
        else:
            mode = os.stat(suid_path).st_mode
            if not (mode & stat.S_ISUID):
                score += 2.0

    # 2. Compromised user shell set to nologin in /etc/passwd
    passwd_path = hidden_state.get("passwd_path", sandbox_path(hidden_state, "/etc/passwd"))
    try:
        content = open(passwd_path).read()
        for line in content.splitlines():
            if line.startswith(f"{user}:") and "/nologin" in line:
                score += 1.5
                break
    except Exception:
        pass

    # 3. Attacker IP in hosts.deny
    deny = sandbox_path(hidden_state, "/etc/hosts.deny")
    try:
        content = open(deny).read()
        if attacker_ip in content:
            score += 1.5
    except Exception:
        pass

    return score


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
    deny_path = sandbox_path(hidden_state, "/etc/hosts.deny")

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
    """FD Leak: agent must explicitly kill the leaker process."""
    target_pid = hidden_state.get("target_pid")

    # Guard: setup never ran on non-Linux
    if target_pid is None:
        return 0.0

    # CRITICAL: Require explicit agent action — prevents false-success from external kills
    if not hidden_state.get("agent_killed_target", False):
        return 0.0

    if IS_LINUX:
        try:
            # Signal 0 = check existence; OSError means process is gone
            os.kill(target_pid, 0)
            return 0.0  # Still alive
        except OSError:
            return 5.0  # Confirmed dead
        except Exception:
            return 0.0
    else:
        killed_file = sandbox_path(hidden_state, "/var/run/killed_pids.txt")
        if os.path.exists(killed_file):
            with open(killed_file) as f:
                if str(target_pid) in f.read():
                    return 5.0
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
    suid_files = hidden_state.get("suid_files", [])
    if not suid_files: return 0.0
    for f in suid_files:
        if not os.path.exists(f):
            pass
        else:
            mode = os.stat(f).st_mode
            if mode & stat.S_ISUID:
                return 0.0
    return 5.0


def grade_task_12(hidden_state: dict) -> float:
    """Sudoers cleanup — checks /etc/sudoers AND all files under /etc/sudoers.d/."""
    bad_entries = hidden_state.get("bad_entries", ["NOPASSWD: ALL"])
    if not bad_entries:
        return 0.0

    sudoers_main = sandbox_path(hidden_state, "/etc/sudoers")
    sudoers_d_dir = sandbox_path(hidden_state, "/etc/sudoers.d")

    # Collect all sudoers files to inspect
    files_to_check = []
    if os.path.exists(sudoers_main):
        files_to_check.append(sudoers_main)
    if os.path.isdir(sudoers_d_dir):
        for fname in os.listdir(sudoers_d_dir):
            fpath = os.path.join(sudoers_d_dir, fname)
            if os.path.isfile(fpath):
                files_to_check.append(fpath)

    # Need at least one file to be meaningful
    if not files_to_check:
        return 0.0

    try:
        # Optional syntax check on Linux (only main file — visudo -c -f)
        if IS_LINUX and os.path.exists(sudoers_main):
            res = subprocess.run(
                ["visudo", "-c", "-f", sudoers_main], capture_output=True
            )
            if res.returncode != 0:
                return 0.0

        # Check every file: no bad entry may appear uncommented
        for fpath in files_to_check:
            with open(fpath, "r") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    for bad in bad_entries:
                        if bad in stripped:
                            return 0.0  # Bad entry still present

        return 5.0

    except Exception:
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

    if intentional_writable and os.path.exists(intentional_writable):
        mode = os.stat(intentional_writable).st_mode
        if mode & 0o002 == 0:
            return 2.5

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
    """Config Drift Detection: config matches gold, env fixed, ownership fixed."""
    if hidden_state.get("stub"):
        return 0.0
    score = 0.0

    # 1. Config file matches gold values
    config_path = hidden_state.get("config_path", "")
    try:
        content = open(config_path).read()
        if "db.internal" in content:
            score += 1.0
        if "5432" in content:
            score += 1.0
        if "WARN" in content:
            score += 0.5
        if "max_connections: 100" in content:
            score += 0.5
    except Exception:
        pass

    # 2. .env file corrected
    env_file = hidden_state.get("env_file", "")
    try:
        content = open(env_file).read()
        if "db.internal" in content and "5432" in content:
            score += 1.0
        if "production" in content:
            score += 0.5
    except Exception:
        pass

    # 3. Ownership fixed
    try:
        import os as _os
        owner_file = _os.path.join(_os.path.dirname(config_path), ".owner")
        content = open(owner_file).read()
        if "appuser" in content:
            score += 0.5
    except Exception:
        pass

    return score
