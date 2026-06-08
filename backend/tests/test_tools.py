"""Tests for tool system."""
import pytest
from backend.tools.registry import ToolRegistry, ToolResult


class TestToolRegistry:
    @pytest.mark.asyncio
    async def test_register_and_execute(self):
        registry = ToolRegistry()

        @registry.register(
            name="echo",
            description="Echo input",
            parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
            },
        )
        async def echo(msg: str = "hello"):
            return f"Echo: {msg}"

        assert registry.count == 1
        assert registry.list_tools()[0]["name"] == "echo"

        result = await registry.execute("echo", {"msg": "test"})
        assert result.success
        assert result.data == "Echo: test"

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        registry = ToolRegistry()
        result = await registry.execute("nonexistent", {})
        assert not result.success
        assert "Unknown tool" in result.error

    def test_list_tools_by_category(self):
        registry = ToolRegistry()

        @registry.register(name="a1", description="t1", category="system")
        def a1():
            pass

        @registry.register(name="a2", description="t2", category="web")
        def a2():
            pass

        system_tools = registry.list_tools(category="system")
        assert len(system_tools) == 1
        assert system_tools[0]["name"] == "a1"


class TestSandboxedExecutor:
    @pytest.mark.asyncio
    async def test_blocked_command(self):
        from backend.tools.sandbox import SandboxedExecutor
        result = await SandboxedExecutor.execute("rm -rf /")
        assert not result["success"]

    @pytest.mark.asyncio
    async def test_command_timeout(self):
        from backend.tools.sandbox import SandboxedExecutor
        # Use python3 (whitelisted) with a long sleep
        result = await SandboxedExecutor.execute('python3 -c "import time; time.sleep(100)"', timeout=1)
        assert not result["success"]
        # Should error due to timeout or blocked pattern
