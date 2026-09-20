"""Multi-agent ticket triage on LangGraph, with a swappable decision engine.

The graph topology, policy and control flow are identical across engines.
Only the *judgment* layer changes, which is what the benchmark measures.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
