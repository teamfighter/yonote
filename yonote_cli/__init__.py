"""Compatibility wrapper for the nested yonote_cli package.

This repository's source layout keeps the actual CLI implementation in the
``yonote_cli/yonote_cli`` package so that it can be packaged with setuptools.
When running directly from a source checkout, however, tests and ``python -m``
expect ``yonote_cli`` to be importable as a top level package.  This module
re-exports the inner package's public modules to provide that compatibility.
"""

from importlib import import_module as _import_module
import sys as _sys

_inner = _import_module(".yonote_cli", __name__)
_core = _import_module(".yonote_cli.core", __name__)
_commands = _import_module(".yonote_cli.commands", __name__)

__all__ = ["__version__", "core", "commands"]
__version__ = getattr(_inner, "__version__", "0")
core = _core
commands = _commands

# Expose submodules so ``import yonote_cli.commands`` works
_sys.modules[__name__ + ".core"] = _core
_sys.modules[__name__ + ".commands"] = _commands
_sys.modules[__name__ + ".yonote_cli"] = _inner

# Ensure package behaves like the inner implementation for submodule discovery
__path__ = _inner.__path__
