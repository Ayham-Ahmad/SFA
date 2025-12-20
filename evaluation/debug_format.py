"""Debug worker output to see actual SQL format"""
import sys
sys.path.insert(0, '.')

from backend.agents.planner import plan_task
from backend.agents.worker import execute_step
from backend.routing import extract_steps

query = "What was the total revenue in 2024?"
plan = plan_task(query, graph_allowed=False)

print("="*60)
print("PLAN OUTPUT:")
print("="*60)
print(repr(plan))

steps = extract_steps(plan)
print("\n" + "="*60)
print(f"EXTRACTED STEPS ({len(steps)}):")
print("="*60)
for i, step in enumerate(steps):
    print(f"{i+1}. {repr(step)}")

print("\n" + "="*60)
print("WORKER OUTPUT (first step):")
print("="*60)
if steps:
    clean_step = steps[0].replace("**", "")
    result = execute_step(clean_step)
    print(repr(result[:500]))
