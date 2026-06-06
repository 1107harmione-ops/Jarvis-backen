"""
tool_registry.py — Central registry for all executable tools.
"""
import logging
from typing import Callable, Dict, Optional

logger = logging.getLogger("tool_registry")

ToolFn = Callable[..., dict]


class ToolRegistry:
    """Registry mapping tool names to their handler functions and metadata."""

    def __init__(self):
        self._tools: Dict[str, dict] = {}

    def register(self, name: str, handler: ToolFn, description: str = "",
                 parameters: dict = None) -> None:
        """Register a tool with its handler and metadata."""
        self._tools[name] = {
            "name": name,
            "handler": handler,
            "description": description,
            "parameters": parameters or {},
        }
        logger.debug("Registered tool: %s", name)

    def get(self, name: str) -> Optional[dict]:
        return self._tools.get(name)

    def execute(self, name: str, **kwargs) -> dict:
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "error": f"Tool '{name}' not found"}
        try:
            result = tool["handler"](**kwargs)
            if isinstance(result, dict):
                return result
            return {"success": True, "result": str(result)}
        except Exception as e:
            logger.error("Tool '%s' failed: %s", name, e)
            return {"success": False, "error": str(e)}

    def list_tools(self) -> list:
        return [{"name": n, "description": t["description"],
                 "parameters": t["parameters"]}
                for n, t in self._tools.items()]

    def has_tool(self, name: str) -> bool:
        return name in self._tools


# Global instance
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    return _registry


import importlib, pkgutil

def discover_tools(tools_package: str = "tools") -> ToolRegistry:
    """Auto-discover and register all tools in the tools package."""
    try:
        pkg = importlib.import_module(tools_package)
    except ImportError:
        logger.warning("Tools package '%s' not found", tools_package)
        return _registry

    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"{tools_package}.{modname}")
            if hasattr(mod, "register"):
                mod.register(_registry)
                logger.info("Discovered tool: %s.%s", tools_package, modname)
        except Exception as e:
            logger.warning("Failed to load tool '%s': %s", modname, e)

    return _registry
