"""Auto-discover and load tool modules.

Call :func:`load_all_tools` during application startup so that every
Python module under ``backend/tools/`` is imported, triggering the
``@registry.register(...)`` decorators in :mod:`backend.tools.builtin`
and any third-party tool modules dropped into the same package.
"""
import importlib
import pkgutil
from pathlib import Path

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Module names that are **not** tool-provider modules and should be
# skipped during auto-discovery.
_SKIP_MODULES: frozenset[str] = frozenset({
    "__init__",
    "registry",
    "sandbox",
    "loader",
})


def load_all_tools() -> None:
    """Import every tool-provider submodule so registrations fire.

    This function iterates over all Python modules in the
    ``backend.tools`` package, imports each one, and logs the total
    count of tools that were registered as a side-effect.
    """
    tools_dir = Path(__file__).parent

    for importer, modname, ispkg in pkgutil.iter_modules([str(tools_dir)]):
        if modname in _SKIP_MODULES:
            continue
        try:
            importlib.import_module(f"backend.tools.{modname}")
            logger.debug(f"Loaded tool module: {modname}")
        except Exception as exc:
            logger.error(f"Failed to load tool module '{modname}': {exc}")

    from backend.tools import registry

    logger.info(f"Tool registry: {registry.count} tools loaded")
