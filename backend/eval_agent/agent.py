"""
agent.py — adk eval entry point.
adk eval loads parent __init__.py as 'agent' module, then accesses agent.agent.root_agent
"""
import sys
from pathlib import Path

# Ensure backend/ is on path
_backend = Path(__file__).parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from agents_adk.fincampaign_pipeline import fincampaign_pipeline  # noqa: E402

root_agent = fincampaign_pipeline
