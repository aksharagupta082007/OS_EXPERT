from client import OsExpertEnv
from models import SovereignAction

def test_environment():
    print("==========================================")
    print("🧪 Testing OS_EXPERT_ENV Pipeline")
    print("==========================================\n")

    with OsExpertEnv(base_url="http://localhost:8000").sync() as env:
        # 1. Test Reset
        print("1️⃣ Sending /reset for Task 1 (Stale Temp Purge)...")
        try:
            result = env.reset(task_id=1)
            obs = result.observation
            print("✅ Environment Reset Successfully!")
            print(f"   Reward: {obs.reward}")
            print(f"   Initial pwd: {obs.system_snapshot.get('pwd', 'N/A')}\n")
        except Exception as e:
            print(f"❌ Failed to reach server. Error: {e}")
            return

        # 2. Test Safe Action
        print("2️⃣ Sending Safe Action (Listing /tmp)...")
        action = SovereignAction(tool="fs.list", params={"path": "/tmp"})
        result = env.step(action)
        obs = result.observation
        print("✅ Action Executed!")
        print(f"   Status: {obs.tool_result.status}")
        print(f"   Reward: {obs.reward}\n")

        # 3. Test Safety Oracle
        print("3️⃣ Sending Destructive Action (rm -rf /)...")
        unsafe_action = SovereignAction(tool="sys.exec", params={"command": "rm -rf /"})
        result = env.step(unsafe_action)
        obs = result.observation
        print("🛡️ Safety Oracle Result:")
        print(f"   Status: {obs.tool_result.status}")
        print(f"   Output: {obs.tool_result.stdout}")
        print(f"   Penalty Reward: {obs.reward}")
        print(f"   Episode Terminated (Done): {obs.done}\n")
        
        if obs.reward < 0 and obs.done:
            print("🎉 SUCCESS: The Safety Oracle successfully blocked the command and penalized the agent!")
        else:
            print("❌ FAILURE: The safety oracle did not trigger correctly.")

if __name__ == "__main__":
    test_environment()
