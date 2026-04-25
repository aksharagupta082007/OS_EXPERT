"""
PPO Training Script for OS_EXPERT_ENV using Hugging Face TRL.

This script demonstrates how to connect a 1B-7B parameter LLM to the 
OS_EXPERT_ENV using the OpenEnv client and train it via PPO.

Prerequisites:
  pip install trl transformers peft torch
"""

import os
import torch
import random
import json
from transformers import AutoTokenizer
from trl import AutoModelForCausalLMWithValueHead, PPOConfig, PPOTrainer

# Import the environment client
from client import EnvClient
from models import SovereignAction

# 1. Configuration
MODEL_NAME = "Qwen/Qwen1.5-1.8B-Chat" # Example 1.8B model, adjust as needed
SERVER_URL = "http://localhost:8000"
NUM_EPOCHS = 100
MAX_STEPS_PER_EPISODE = 15

def format_prompt(system_snapshot: dict) -> str:
    """Format the system snapshot into a prompt for the LLM."""
    prompt = "You are a Senior Linux System Administrator. Your task is to fix the broken state of the system.\n"
    prompt += "Current System State:\n"
    prompt += json.dumps(system_snapshot, indent=2)
    prompt += "\n\nRespond with a JSON tool call to fix the issue."
    return prompt

def parse_action(llm_output: str) -> SovereignAction:
    """
    Parse the LLM text output into a SovereignAction.
    In a real scenario, you'd want robust JSON parsing/regex here.
    """
    # Placeholder: assume LLM outputs clean JSON for the tool call
    try:
        data = json.loads(llm_output)
        return SovereignAction(**data)
    except Exception:
        # Fallback to a harmless read command if parsing fails
        return SovereignAction(tool="fs.read", params={"path": "/etc/os-release"})

def main():
    print(f"Loading Model {MODEL_NAME}...")
    
    # Initialize tokenizer and model with value head for PPO
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLMWithValueHead.from_pretrained(
        MODEL_NAME, 
        device_map="auto", 
        torch_dtype=torch.bfloat16
    )
    
    # Initialize PPO Trainer
    ppo_config = PPOConfig(
        batch_size=16,
        mini_batch_size=4,
        learning_rate=1.41e-5,
    )
    
    ppo_trainer = PPOTrainer(
        config=ppo_config, 
        model=model, 
        ref_model=None, # TRL will auto-create ref_model
        tokenizer=tokenizer
    )

    print("Connecting to OS_EXPERT_ENV server...")
    
    # 2. Connect to the Sandbox
    with EnvClient(base_url=SERVER_URL) as env:
        for epoch in range(NUM_EPOCHS):
            # Select a random task template (1 to 15)
            task_id = random.randint(1, 15)
            print(f"\n--- Epoch {epoch+1}/{NUM_EPOCHS} | Task {task_id} ---")
            
            # Reset environment
            result = env.reset(task_id=task_id)
            obs = result.observation
            
            prompt = format_prompt(obs.system_snapshot)
            input_tensor = tokenizer.encode(prompt, return_tensors="pt").squeeze(0).to(model.pretrained_model.device)
            
            done = False
            step = 0
            
            # Trajectory buffers
            trajectory_queries = []
            trajectory_responses = []
            trajectory_rewards = []
            
            while not done and step < MAX_STEPS_PER_EPISODE:
                # 3. Generate Action
                response_tensor = ppo_trainer.generate(
                    input_tensor.unsqueeze(0), 
                    max_new_tokens=128,
                    pad_token_id=tokenizer.eos_token_id
                ).squeeze(0)
                
                # Extract only the newly generated tokens
                generated_tokens = response_tensor[len(input_tensor):]
                action_text = tokenizer.decode(generated_tokens, skip_special_tokens=True)
                
                parsed_action = parse_action(action_text)
                print(f"Step {step+1} Action: {parsed_action.tool}")
                
                # 4. Execute in Sandbox
                step_result = env.step(parsed_action)
                obs = step_result.observation
                
                # Store trajectory
                trajectory_queries.append(input_tensor)
                trajectory_responses.append(generated_tokens)
                trajectory_rewards.append(torch.tensor(obs.reward, dtype=torch.float32))
                
                if obs.done:
                    done = True
                    print(f"Episode finished! Final Reward: {obs.reward}")
                else:
                    # Append result to prompt for next step
                    prompt += f"\nAction taken: {action_text}\nResult: {obs.tool_result.stdout}\n"
                    input_tensor = tokenizer.encode(prompt, return_tensors="pt").squeeze(0).to(model.pretrained_model.device)
                    
                step += 1
                
            # 5. PPO Update
            print("Running PPO Update...")
            stats = ppo_trainer.step(trajectory_queries, trajectory_responses, trajectory_rewards)
            print(f"PPO Loss: {stats['ppo/loss/total']}")

if __name__ == "__main__":
    main()
