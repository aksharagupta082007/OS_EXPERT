# ===========================================================================
# OS_EXPERT_ENV — Unified Single-Container Dockerfile
#
# Compatible with Hugging Face Spaces (single Docker process).
# Installs all sysadmin tools into the container, then snapshots a
# "Gold Rootfs" at /opt/gold_rootfs. At runtime, the server copies
# this snapshot into /tmp/active_sandbox on each reset() and executes
# agent commands inside it via chroot.
#
# Build:
#   docker build -t os-expert-env:latest .
# ===========================================================================

ARG BASE_IMAGE=ghcr.io/meta-pytorch/openenv-base:latest
FROM ${BASE_IMAGE} AS builder

WORKDIR /app

# Ensure git is available (required for installing dependencies from VCS)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Build argument to control whether we're building standalone or in-repo
ARG BUILD_MODE=in-repo
ARG ENV_NAME=os_expert_env

# Copy environment code (always at root of build context)
COPY . /app/env

# For in-repo builds, openenv is already vendored in the build context
# For standalone builds, openenv will be installed via pyproject.toml
WORKDIR /app/env

# Ensure uv is available (for local builds where base image lacks it)
RUN if ! command -v uv >/dev/null 2>&1; then \
        curl -LsSf https://astral.sh/uv/install.sh | sh && \
        mv /root/.local/bin/uv /usr/local/bin/uv && \
        mv /root/.local/bin/uvx /usr/local/bin/uvx; \
    fi

# Install dependencies using uv sync
# If uv.lock exists, use it; otherwise resolve on the fly
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f uv.lock ]; then \
        uv sync --frozen --no-install-project --no-editable; \
    else \
        uv sync --no-install-project --no-editable; \
    fi

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f uv.lock ]; then \
        uv sync --frozen --no-editable; \
    else \
        uv sync --no-editable; \
    fi


# ==========================  FINAL RUNTIME STAGE  ==========================
FROM ${BASE_IMAGE}

WORKDIR /home/user/app

# Avoid interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive

# ---------------------------------------------------------------------------
# Install ALL sysadmin / security / network tools directly into the image
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core utilities
    coreutils findutils grep sed gawk diffutils \
    # Editors & pagers
    nano less \
    # Process & system
    procps psmisc sysstat \
    # Networking
    iproute2 iputils-ping net-tools curl wget \
    nmap traceroute dnsutils tcpdump netcat-openbsd \
    # Web server (realistic scenario target)
    nginx \
    # SSH
    openssh-server openssh-client \
    # Firewall
    iptables \
    # Python (for scripting scenarios inside sandbox)
    python3 \
    # Security / Audit
    debsums \
    # Logging & cron
    rsyslog cron logrotate \
    # Misc
    sudo file tree jq lsof bash-completion ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Build the Gold Rootfs at /opt/gold_rootfs
# This is the pristine snapshot that gets copied into /tmp/active_sandbox
# on every reset(). It contains ONLY the OS filesystem — never the server
# code, .venv, or .git.
# ---------------------------------------------------------------------------

RUN mkdir -p /opt/gold_rootfs

# Copy essential OS directories into the Gold Rootfs
RUN for dir in bin etc lib lib64 sbin usr var opt; do \
        if [ -d "/$dir" ]; then \
            cp -a "/$dir" "/opt/gold_rootfs/$dir" || true; \
        fi ; \
    done

# Create standard directory structure inside gold rootfs
RUN mkdir -p /opt/gold_rootfs/tmp \
             /opt/gold_rootfs/root \
             /opt/gold_rootfs/home \
             /opt/gold_rootfs/run \
             /opt/gold_rootfs/dev \
             /opt/gold_rootfs/proc \
             /opt/gold_rootfs/sys \
             /opt/gold_rootfs/var/log \
             /opt/gold_rootfs/var/run \
             /opt/gold_rootfs/var/www/html \
             /opt/gold_rootfs/etc/nginx/sites-available

# Create realistic users inside the gold rootfs
RUN chroot /opt/gold_rootfs /bin/bash -c " \
    useradd -m -s /bin/bash sysadmin 2>/dev/null; \
    echo 'sysadmin:changeme' | chpasswd; \
    useradd -m -s /bin/bash developer 2>/dev/null; \
    echo 'developer:devpass' | chpasswd; \
    useradd -m -s /bin/bash webmaster 2>/dev/null; \
    echo 'webmaster:webpass' | chpasswd; \
    usermod -aG sudo sysadmin 2>/dev/null; \
    true"

# Generate SSH host keys inside gold rootfs
RUN chroot /opt/gold_rootfs /bin/bash -c "ssh-keygen -A 2>/dev/null; true"

# Sample nginx config
RUN echo 'server { listen 80 default_server; root /var/www/html; index index.html; }' \
    > /opt/gold_rootfs/etc/nginx/sites-available/default 2>/dev/null || true

# Sample web content
RUN echo '<html><body><h1>OS Expert Sandbox</h1></body></html>' \
    > /opt/gold_rootfs/var/www/html/index.html

# Seed realistic log entries
RUN echo "Jan 01 00:00:01 sandbox sshd[1234]: Accepted publickey for sysadmin from 10.0.0.1 port 22" \
    >> /opt/gold_rootfs/var/log/auth.log && \
    echo "Jan 01 00:01:22 sandbox sshd[1235]: Failed password for root from 10.0.0.99 port 22" \
    >> /opt/gold_rootfs/var/log/auth.log && \
    echo "Jan 01 00:02:45 sandbox sshd[1236]: Failed password for admin from 192.168.1.100 port 22" \
    >> /opt/gold_rootfs/var/log/auth.log && \
    echo "Jan 01 00:03:10 sandbox kernel: [UFW BLOCK] IN=eth0 OUT= SRC=10.0.0.50 DST=10.0.0.1" \
    >> /opt/gold_rootfs/var/log/syslog && \
    echo "Jan 01 00:00:01 sandbox CRON[999]: (root) CMD (/usr/sbin/logrotate /etc/logrotate.conf)" \
    >> /opt/gold_rootfs/var/log/syslog

# Create the gold rootfs baseline marker (used by fs.compare_versions)
RUN echo "gold_rootfs_built=$(date -u +%Y%m%dT%H%M%SZ)" > /opt/gold_rootfs/etc/gold_marker

# Production marker file
RUN echo "1.0.0-production" > /opt/gold_rootfs/etc/os_expert_version

# ---------------------------------------------------------------------------
# Ensure the gold rootfs does NOT contain server files
# ---------------------------------------------------------------------------
RUN rm -rf /opt/gold_rootfs/home/user/app 2>/dev/null || true && \
    rm -rf /opt/gold_rootfs/app 2>/dev/null || true

# ---------------------------------------------------------------------------
# Copy virtualenv and project from builder
# ---------------------------------------------------------------------------
COPY --from=builder /app/env/.venv /home/user/app/.venv
COPY --from=builder /app/env /home/user/app/env

# Set PATH to use the virtual environment
ENV PATH="/home/user/app/.venv/bin:$PATH"

# Set PYTHONPATH so imports work correctly
ENV PYTHONPATH="/home/user/app/env:$PYTHONPATH"

# Gold rootfs path (used by world_state.py)
ENV GOLD_ROOTFS_PATH="/opt/gold_rootfs"
ENV SANDBOX_PATH="/tmp/active_sandbox"

# Prepare the sandbox directory
RUN mkdir -p /tmp/active_sandbox

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the FastAPI server
CMD ["sh", "-c", "cd /home/user/app/env && /home/user/app/.venv/bin/python -m uvicorn server.app:app --host 0.0.0.0 --port 8000"]
