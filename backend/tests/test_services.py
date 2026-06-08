"""Tests for service layer."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.auth import AuthService
from backend.services.conversation import ConversationService


class TestAuthService:
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """Test login with invalid username raises ValueError."""
        db_mock = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db_mock.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Invalid username or password"):
            await AuthService.login_user(db_mock, "nonexistent", "wrongpass")


class TestConversationService:
    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(self):
        """Test fetching a nonexistent conversation returns None."""
        db_mock = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db_mock.execute.return_value = mock_result

        from uuid import UUID
        result = await ConversationService.get_conversation(
            db_mock,
            UUID("00000000-0000-0000-0000-000000000000"),
            UUID("00000000-0000-0000-0000-000000000000"),
        )
        assert result is None
