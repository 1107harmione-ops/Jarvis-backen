"""Tests for memory management system."""
import pytest
from unittest.mock import AsyncMock, patch
from backend.memory.manager import MemoryManager


class TestMemoryManager:
    @pytest.mark.asyncio
    async def test_store_memory(self):
        db_mock = AsyncMock()
        manager = MemoryManager()

        from uuid import UUID
        result = await manager.store(
            db_mock,
            UUID("12345678-1234-5678-1234-567812345678"),
            "Test memory content",
            memory_type="semantic",
            importance="high",
        )

        assert result["memory_type"] == "semantic"
        assert result["importance"] == "high"
        assert "id" in result

    @pytest.mark.asyncio
    async def test_search_keyword_fallback(self):
        """Test keyword search when vector search unavailable."""
        from unittest.mock import MagicMock
        db_mock = AsyncMock()
        # Use MagicMock for the await result so scalars().all() works synchronously
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db_mock.execute.return_value = mock_result

        manager = MemoryManager()
        from uuid import UUID
        results = await manager.search(
            db_mock,
            UUID("12345678-1234-5678-1234-567812345678"),
            "test query",
            limit=5,
        )

        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_forget_nonexistent(self):
        from unittest.mock import MagicMock
        db_mock = AsyncMock()
        # Use MagicMock so scalar_one_or_none() works synchronously
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db_mock.execute.return_value = mock_result

        manager = MemoryManager()
        from uuid import UUID
        result = await manager.forget(
            db_mock,
            UUID("00000000-0000-0000-0000-000000000000"),
            UUID("00000000-0000-0000-0000-000000000000"),
        )

        assert not result
