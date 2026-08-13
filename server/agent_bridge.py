"""Makes backend/ importable and re-exports the agent.

The backend modules import each other flatly (`from prompts import SYSTEM`),
so backend/ itself must be on sys.path — importing them as `backend.agent`
would break those flat imports.
"""
import os
import sys

BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from agent import Conversation  # noqa: E402  (must follow the sys.path insert)

__all__ = ["Conversation"]
