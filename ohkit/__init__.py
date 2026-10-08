"""A unified Python API for coding agents.

This pre-alpha bootstrap exposes package metadata only. Agent backends and
execution APIs are not implemented yet.
"""

from importlib.metadata import version

__all__ = ["__version__"]
__version__ = version("ohkit")
