"""Department subgraphs, each compiled independently and attached as a node."""

from __future__ import annotations

from . import billing, escalation, technical

__all__ = ["billing", "escalation", "technical"]
