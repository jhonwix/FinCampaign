"""eval_agent package — wrapper for adk eval.
adk eval loads this __init__.py as module 'agent', then accesses agent.agent.root_agent.
We load agent.py via importlib to avoid package-name collisions.
"""
import importlib.util
from pathlib import Path

_agent_path = Path(__file__).parent / "agent.py"
spec = importlib.util.spec_from_file_location("agent_sub", str(_agent_path))
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)
