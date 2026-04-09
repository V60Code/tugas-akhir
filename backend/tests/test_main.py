"""
Unit tests for app.main — lifespan startup / shutdown behavior.

We call the lifespan context manager directly rather than spinning up a full
ASGI server, because httpx ASGITransport does not trigger ASGI lifespan events.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from app.main import app, lifespan


class TestLifespan:

    @pytest.mark.asyncio
    async def test_startup_calls_ensure_bucket_exists(self):
        """Lifespan startup must call minio_service.ensure_bucket_exists()."""
        mock_minio = MagicMock()

        with patch("app.services.storage.minio_service", mock_minio):
            async with lifespan(app):
                pass

        mock_minio.ensure_bucket_exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_continues_if_minio_unavailable(self):
        """If MinIO raises during startup the lifespan still completes — no crash."""
        mock_minio = MagicMock()
        mock_minio.ensure_bucket_exists.side_effect = Exception("connection refused")

        # Should NOT raise
        with patch("app.services.storage.minio_service", mock_minio):
            async with lifespan(app):
                pass
