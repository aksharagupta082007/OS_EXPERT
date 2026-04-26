---
title: Os Expert Environment Server
emoji: 🌟
colorFrom: yellow
colorTo: red
sdk: docker
pinned: false
app_port: 8000
base_path: /
sleep_timeout: null
tags:
  - openenv
---

# OS_EXPERT_ENV: The Forensic "Detective Gym" for LLMs

### Can an 8B model learn to be an Elite SRE — from scratch?

We gave a language model a shell, a live Linux kernel, and 15 broken systems. We didn't just ask it to call tools; we asked it to diagnose forensic anomalies that no simple command can fix. 

**This is OS_EXPERT_ENV** — a self-improving environment where an RL agent learns to diagnose and resolve real production Linux failures through "Sovereign" system dynamics, adversarial safety gating, and GRPO-ready trajectory gathering.

> **Bangalore OpenEnv Hackathon 2026 Submission** | Built with [OpenEnv](https://github.com/meta-pytorch/OpenEnv) | Deployed on [HF Spaces](https://aksharaguptahehehehehe-os-expert-env.hf.space) | Training via [Unsloth](https://github.com/unslothai/unsloth) in [Colab](https://colab.research.google.com/drive/1u4QYtwWQ_I7gGOdJ9zFW9SQNeautELB5)

---

## 📖 The Story: From "Tool-Caller" to "System Detective"

### 🌑 Phase 1: The Illusion of Competence
Early in development, our agent was a "Tool Caller." It could run `ls` and `cat`, but it lacked reasoning. Our initial logs showed an agent "Reward Hacking"—receiving points for accidentally fixing problems it didn't understand or stumbling into success because the environment was too fragile. It was a "Mock" world where real system signals were missing.

### ⚡ Phase 2: The Infrastructure Crisis
As we scaled to the full 15-task suite, the system broke. We hit the **"Cascade of Reconnect"** failures. The environment crashed when the agent touched the firewall, and the LLM (Llama-3.1-8B) choked on its own context window, hitting the 8,192 token wall. We realized that a simple simulator wouldn't cut it. To build a truly **Sovereign Agent**, we had to build a **Sovereign Environment**.

### 🌟 Phase 3: The Sovereign Pivot
We moved away from mocks and implemented real **Linux Kernel Dynamics**. We used `os.fork()` to create genuine **Zombie Processes** and `os.unlink()` on open handles to create **File Descriptor Leaks**. We built a **Safety Oracle** with an explicit "Allowed Writes" table to let the agent fix `/etc/sudoers` without burning down the host.

**Today, OS_EXPERT_ENV is a Forensic Detective Gym that demands reasoning over simple automation.**

---

## 🔧 Environment Innovation: The "Sovereign 15"

We have implemented 15 deterministic tasks that test "Detective Reasoning" across four high-stakes categories:

| Category | Forensic Challenge | Innovation |
| :--- | :--- | :--- |
| **Kernel Forensics** | **Zombie Reaping (T4)** | The agent cannot just `kill -9`. It must identify the parent and signal it to reap the child. |
| **Resource Leaks** | **Deleted-Open FDs (T9)** | `df` says the disk is full, but `du` says it's empty. The agent must trace the FD handle back to a leaked PID. |
| **Security Audits** | **Sudoers/SUID (T11/12)** | The agent must distinguish between authorized configs and rogue backdoors using kernel stat checks. |
| **Network Triage** | **Port Hijacking (T5)** | A rogue process is aggressively binding to production ports. The agent must use `net.ports` to find the interloper. |

---

## 🧠 Core Innovations & Safety Architecture

Built on the **OpenEnv Framework**, our environment prioritizes **Forensic Realism** and **Host Stability**.

1. **The Safety Oracle:** A robust gating system that prevents destructive commands (like `rm -rf /`) while allowing surgical edits to protected files (like `/etc/hosts`) only for authorized task IDs.
2. **Dense Reward Rubric:** $R_{total} = R_{outcome} + R_{process} + R_{safety} - P_{risk} - P_{steps}$. This rewards the *journey* (finding clues) as much as the *destination* (fixing the bug).
3. **Context Sliding Window:** A proprietary "Pinned Header" strategy that keeps the System Prompt and Task instructions pinned at the top while cycling out stale step history to prevent context overflows.
4. **Lazy Reconnection:** A resilient client-side logic that detects Hugging Face Space hibernation, pings the `/health` endpoint, and re-establishes the WebSocket connection without losing task progress.

---

## 📈 Training Evidence: Showing the Growth

We used **Expert Iteration** with **GRPO logic** to train a **Qwen2.5-1.5B** agent. The results prove that system forensics is a learnable skill.

### 📊 Performance Summary
* **Initial Avg Reward:** -0.155 (Baseline agents frequently hit Safety Oracle "walls" or failed to find hidden leaks).
* **Post-Training Avg Reward:** **+3.669** (The agent learned to use specialized forensic tools and investigate before acting).
* **Safety:** Near-zero rate of "Recursive chmod Hacking" as the agent learned that specific file fixes yield higher rewards than world-writable blanket permissions.

---

## Quick Start & Deployment

### 1. Run Inference
```python
from client import OsExpertEnv
from models import SovereignAction

# Connect to the live "Detective Gym"
with OsExpertEnv(base_url="https://aksharaguptahehehehehe-os-expert-env.hf.space") as env:
    result = env.reset(task_id=4)
    print(f"Goal: {result.observation.system_snapshot['task_description']}")
    
    # Example action: list processes to find zombies
    result = env.step(SovereignAction(tool="proc.list", params={}))
    print(result.observation.tool_result.stdout)
```

### 2. Deploy to HF Spaces
```bash
# From the environment directory
openenv push --repo-id your-username/os-expert-env
```

## 📂 Project Structure
```
os_expert_env/
├── client.py              # Sovereign WebSocket client with lazy reconnect
├── inference.py           # RL evaluation script with context management
├── pipeline/
│   ├── project_templates.py # The "Sovereign 15" setup logic (os.fork, etc.)
│   └── episode_generator.py # Episode initialization
├── reward/
│   ├── aggregator.py      # Dense reward calculation (R_total)
│   ├── grader.py          # Deterministic Python-based outcome checkers
│   └── safety_oracle.py   # Task-aware security gating
└── env/
    ├── action_router.py   # 35-tool inventory & Linux-native shims
    └── world_state.py     # System state tracking
```

---

**Team:** Future Reward
**Contributors:** Akshara Gupta, Bhavya Jain
