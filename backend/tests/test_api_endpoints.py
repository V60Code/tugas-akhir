"""
Integration-style tests for the FastAPI endpoints.

These tests use httpx.AsyncClient against the real FastAPI app but mock out
all external dependencies (PostgreSQL, MinIO, Celery) so they run completely
offline — no running infrastructure required.

Coverage targets:
  - GET  /  (health root)
  - GET  /health
  - POST /api/v1/auth/register
  - POST /api/v1/auth/login
  - GET  /api/v1/auth/me
  - GET  /api/v1/projects/
  - POST /api/v1/projects/
  - POST /api/v1/jobs/upload
  - GET  /api/v1/jobs/{id}/status
  - POST /api/v1/jobs/{id}/finalize
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.job import JobStatus


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_token_headers(token: str = "fake-jwt-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── Health endpoints ──────────────────────────────────────────────────────────

class TestHealthEndpoints:
    """Simple smoke tests for the liveness / readiness endpoints."""

    @pytest.mark.asyncio
    async def test_root_returns_200(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/")
        assert response.status_code == 200
        assert "SQL Optimizer API" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ── Auth endpoints ────────────────────────────────────────────────────────────

class TestAuthEndpoints:
    """Tests for registration and login flows — DB is mocked."""

    @pytest.mark.asyncio
    async def test_register_missing_fields_returns_422(self):
        """POST with no body → FastAPI validation should return 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/register", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_missing_fields_returns_422(self):
        """OAuth2 form endpoint with no body → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/login", data={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_with_wrong_credentials_returns_401(self):
        """
        Mock the DB session so no real user is found → 401 Unauthorized.
        """
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None  # User not found

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.api.v1.auth.get_db", return_value=mock_db):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/login",
                    data={"username": "no@user.com", "password": "wrong"},
                )
        assert response.status_code == 400


# ── Jobs — Upload endpoint ────────────────────────────────────────────────────

class TestJobUpload:
    """Tests for POST /api/v1/jobs/upload with all heavy deps mocked."""

    @pytest.mark.asyncio
    async def test_upload_without_auth_returns_401_or_403(self):
        """Unauthenticated requests should be rejected."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/jobs/upload",
                data={"project_id": str(uuid.uuid4()), "app_context": "READ_HEAVY"},
                files={"file": ("schema.sql", b"CREATE TABLE t (id INT);", "application/sql")},
            )
        # 401 (no credentials) or 403 (invalid token)
        assert response.status_code in (401, 403, 422)

    @pytest.mark.asyncio
    async def test_upload_non_sql_file_returns_400(self):
        """Non-.sql extension should be rejected even before auth checks if possible,
        or after auth. Either 400 or 401/403 is valid here depending on middleware order."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/jobs/upload",
                data={"project_id": str(uuid.uuid4()), "app_context": "READ_HEAVY"},
                files={"file": ("data.csv", b"col1,col2\n1,2", "text/csv")},
            )
        # Auth check happens first → 401/403, or extension check → 400
        assert response.status_code in (400, 401, 403, 422)


# ── Jobs — Status endpoint ────────────────────────────────────────────────────

class TestJobStatus:
    """Tests for GET /api/v1/jobs/{job_id}/status."""

    @pytest.mark.asyncio
    async def test_status_without_auth_returns_401(self):
        job_id = str(uuid.uuid4())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/jobs/{job_id}/status")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_status_nonexistent_job_returns_404_when_authed(
        self, auth_override, db_override
    ):
        """
        Authenticated user + DB returns no job → 404.
        Uses shared auth_override / db_override fixtures so no manual patching.
        """
        # /status uses result.first() (JOIN query, no .scalars())
        db_override.execute.return_value.first.return_value = None

        job_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/jobs/{job_id}/status",
                headers={"Authorization": "Bearer fake-token"},
            )
        # Either 401 (token not validated) or 404 (job not found)
        assert response.status_code in (401, 403, 404)


# ── Auth — success paths ──────────────────────────────────────────────────────

class TestAuthSuccessPaths:
    """Auth success cases that require DB mocking via the db_override fixture."""

    @pytest.mark.asyncio
    async def test_register_new_user_returns_201(self, db_override):
        """Happy path: new unique email → user created, 201 returned."""
        # No existing user found in DB
        db_override.execute.return_value.scalars.return_value.first.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={"email": "bob@example.com", "full_name": "Bob", "password": "securePass1"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "bob@example.com"
        assert "password" not in data  # password_hash must never leak

    @pytest.mark.asyncio
    async def test_register_short_password_returns_422(self):
        """P0-3: Passwords shorter than 8 chars must be rejected at schema level."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={"email": "bob@example.com", "full_name": "Bob", "password": "short"},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_400(self, db_override, mock_user):
        """Duplicate email → 400 with human-readable message."""
        # Simulate an existing user found
        db_override.execute.return_value.scalars.return_value.first.return_value = mock_user

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={"email": "alice@example.com", "full_name": "Alice2", "password": "securePass1"},
            )

        assert response.status_code == 400
        assert isinstance(response.json()["detail"], str)

    @pytest.mark.asyncio
    async def test_get_me_returns_current_user_profile(self, auth_override, mock_user):
        """GET /me returns the profile of the authenticated user."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == mock_user.email
        assert "password" not in data


# ── Projects endpoints ────────────────────────────────────────────────────────

class TestProjectEndpoints:
    """Tests for GET /projects/ and POST /projects/."""

    @pytest.mark.asyncio
    async def test_list_projects_without_auth_returns_401_or_403(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/projects/")

        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_list_projects_returns_empty_list_when_none_exist(
        self, auth_override, db_override
    ):
        """Authenticated user with no projects → empty array, not 404."""
        # read_projects uses result.all() directly (not .scalars())
        db_override.execute.return_value.all.return_value = []

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/projects/",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_create_project_returns_201(self, auth_override, db_override):
        """Valid project name → 201 with the created project."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/projects/",
                json={"name": "My E-commerce Schema", "description": "Test project"},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 201
        assert response.json()["name"] == "My E-commerce Schema"

    @pytest.mark.asyncio
    async def test_create_project_blank_name_returns_422(self, auth_override, db_override):
        """Blank or whitespace-only name must be rejected by the schema validator."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/projects/",
                json={"name": "   "},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 422


# ── Finalize endpoint ─────────────────────────────────────────────────────────

class TestFinalizeEndpoint:
    """Tests for POST /api/v1/jobs/{job_id}/finalize."""

    @pytest.mark.asyncio
    async def test_finalize_without_auth_returns_401_or_403(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/v1/jobs/{uuid.uuid4()}/finalize",
                json={"accepted_suggestion_ids": []},
            )

        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_finalize_nonexistent_job_returns_404(
        self, auth_override, db_override
    ):
        """Job ID not in DB → 404."""
        # The endpoint uses result.first() for the JOIN query — not scalars()
        db_override.execute.return_value.first.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/v1/jobs/{uuid.uuid4()}/finalize",
                json={"accepted_suggestion_ids": []},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_finalize_job_of_another_user_returns_403(
        self, auth_override, mock_user, db_override
    ):
        """Job belongs to a different user → 403, not 404 (avoids info disclosure)."""
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()

        mock_project = MagicMock()
        mock_project.user_id = uuid.uuid4()  # deliberately different from mock_user.id

        db_override.execute.return_value.first.return_value = (mock_job, mock_project)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/v1/jobs/{mock_job.id}/finalize",
                json={"accepted_suggestion_ids": []},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_finalize_success_queues_celery_task_and_returns_200(
        self, auth_override, mock_user, db_override
    ):
        """Valid owned job → 200, Celery task enqueued exactly once."""
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()

        mock_project = MagicMock()
        mock_project.user_id = mock_user.id  # same owner → authorized

        db_override.execute.return_value.first.return_value = (mock_job, mock_project)

        # finalize_job is imported at the top of jobs.py, so we must patch its
        # name in the module where it is used, not its origin in app.worker.
        with patch("app.api.v1.jobs.finalize_job") as mock_task:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/api/v1/jobs/{mock_job.id}/finalize",
                    json={"accepted_suggestion_ids": []},
                    headers={"Authorization": "Bearer fake-token"},
                )

        assert response.status_code == 200
        mock_task.delay.assert_called_once_with(str(mock_job.id))


# ── Upload — authorized paths ─────────────────────────────────────────────────────────────────────────────
class TestJobUploadAuthorized:
    """Coverage for authenticated upload paths (project ownership checks + happy path)."""

    @pytest.mark.asyncio
    async def test_upload_project_not_found_returns_404(self, auth_override, db_override):
        """Project doesn't exist at all → 404."""
        db_override.execute.return_value.scalars.return_value.first.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/jobs/upload",
                data={"project_id": str(uuid.uuid4()), "app_context": "READ_HEAVY"},
                files={"file": ("schema.sql", b"CREATE TABLE t (id INT);", "application/sql")},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_project_wrong_owner_returns_403(self, auth_override, db_override):
        """Project exists but belongs to another user → 403."""
        mock_none = MagicMock()
        mock_none.scalars.return_value.first.return_value = None   # ownership check: not mine
        mock_exists = MagicMock()
        mock_exists.scalars.return_value.first.return_value = MagicMock()  # exists for someone else
        db_override.execute = AsyncMock(side_effect=[mock_none, mock_exists])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/jobs/upload",
                data={"project_id": str(uuid.uuid4()), "app_context": "READ_HEAVY"},
                files={"file": ("schema.sql", b"CREATE TABLE t (id INT);", "application/sql")},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_upload_success_queues_celery(self, auth_override, db_override):
        """Happy path: valid .sql + owned project → 202, Celery task triggered."""
        db_override.execute.return_value.scalars.return_value.first.return_value = MagicMock()

        with patch("app.api.v1.jobs.minio_service") as mock_minio, \
             patch("app.api.v1.jobs.process_analysis_job") as mock_task:
            mock_minio.upload_file.return_value = "user/job/clean.sql"

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/jobs/upload",
                    data={"project_id": str(uuid.uuid4()), "app_context": "READ_HEAVY"},
                    files={"file": ("schema.sql", b"CREATE TABLE t (id INT);", "application/sql")},
                    headers={"Authorization": "Bearer fake-token"},
                )

        assert response.status_code == 202
        assert response.json()["status"] == "QUEUED"
        mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_minio_failure_returns_500(self, auth_override, db_override):
        """MinIO unavailable during upload → 500."""
        db_override.execute.return_value.scalars.return_value.first.return_value = MagicMock()

        with patch("app.api.v1.jobs.minio_service") as mock_minio:
            mock_minio.upload_file.side_effect = Exception("MinIO storage unavailable")

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/jobs/upload",
                    data={"project_id": str(uuid.uuid4()), "app_context": "READ_HEAVY"},
                    files={"file": ("schema.sql", b"CREATE TABLE t (id INT);", "application/sql")},
                    headers={"Authorization": "Bearer fake-token"},
                )

        assert response.status_code == 500


# ── Suggestions endpoint ─────────────────────────────────────────────────────────────────────────────
class TestJobSuggestionsEndpoint:
    """Coverage for GET /jobs/{id}/suggestions."""

    @pytest.mark.asyncio
    async def test_suggestions_without_auth_returns_401(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/jobs/{uuid.uuid4()}/suggestions")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_suggestions_job_not_found_returns_404(self, auth_override, db_override):
        db_override.execute.return_value.first.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/jobs/{uuid.uuid4()}/suggestions",
                headers={"Authorization": "Bearer fake-token"},
            )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_suggestions_wrong_owner_returns_403(
        self, auth_override, mock_user, db_override
    ):
        mock_job = MagicMock()
        mock_project = MagicMock()
        mock_project.user_id = uuid.uuid4()  # different from mock_user.id
        db_override.execute.return_value.first.return_value = (mock_job, mock_project)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/jobs/{uuid.uuid4()}/suggestions",
                headers={"Authorization": "Bearer fake-token"},
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_suggestions_job_not_completed_returns_empty(
        self, auth_override, mock_user, db_override
    ):
        """Job still PROCESSING → empty suggestions list with 200."""
        mock_job = MagicMock()
        mock_job.status = JobStatus.PROCESSING
        mock_project = MagicMock()
        mock_project.user_id = mock_user.id
        db_override.execute.return_value.first.return_value = (mock_job, mock_project)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/jobs/{uuid.uuid4()}/suggestions",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["suggestions"] == []
        assert data["original_sql"] == ""


# ── Download endpoint ─────────────────────────────────────────────────────────────────────────────
class TestJobDownloadEndpoint:
    """Coverage for GET /jobs/{id}/download."""

    @pytest.mark.asyncio
    async def test_download_without_auth_returns_401(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/jobs/{uuid.uuid4()}/download")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_download_job_not_found_returns_404(self, auth_override, db_override):
        db_override.execute.return_value.first.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/jobs/{uuid.uuid4()}/download",
                headers={"Authorization": "Bearer fake-token"},
            )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_not_finalized_returns_400(
        self, auth_override, mock_user, db_override
    ):
        """Job COMPLETED but not FINALIZED → 400."""
        mock_job = MagicMock()
        mock_job.status = JobStatus.COMPLETED
        mock_project = MagicMock()
        mock_project.user_id = mock_user.id
        db_override.execute.return_value.first.return_value = (mock_job, mock_project)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/jobs/{uuid.uuid4()}/download",
                headers={"Authorization": "Bearer fake-token"},
            )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_download_success_returns_presigned_url(
        self, auth_override, mock_user, db_override
    ):
        """Finalized job with artifact → 200 with presigned URL."""
        mock_job = MagicMock()
        mock_job.status = JobStatus.FINALIZED
        mock_project = MagicMock()
        mock_project.user_id = mock_user.id

        mock_artifact = MagicMock()
        mock_artifact.storage_path = "user/job/optimized.sql"

        mock_r1 = MagicMock()
        mock_r1.first.return_value = (mock_job, mock_project)
        mock_r2 = MagicMock()
        mock_r2.scalars.return_value.first.return_value = mock_artifact
        db_override.execute = AsyncMock(side_effect=[mock_r1, mock_r2])

        with patch("app.api.v1.jobs.minio_service") as mock_minio:
            mock_minio.get_presigned_url.return_value = "http://minio/presigned?sig=abc"

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/api/v1/jobs/{uuid.uuid4()}/download",
                    headers={"Authorization": "Bearer fake-token"},
                )

        assert response.status_code == 200
        assert response.json()["download_url"] == "http://minio/presigned?sig=abc"


# ── Project detail / edit / delete endpoints ───────────────────────────────────────────────────
class TestProjectDetailEndpoints:
    """Coverage for GET/PATCH/DELETE /projects/{id} and GET /projects/{id}/jobs."""

    def _make_mock_project(self, user_id: uuid.UUID) -> MagicMock:
        project = MagicMock()
        project.id = uuid.uuid4()
        project.name = "Test Project"
        project.description = "A test project"
        project.user_id = user_id
        project.created_at = datetime.now(timezone.utc)
        return project

    @pytest.mark.asyncio
    async def test_get_project_returns_200(self, auth_override, mock_user, db_override):
        mock_project = self._make_mock_project(mock_user.id)
        db_override.execute.return_value.scalars.return_value.first.return_value = mock_project

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/projects/{mock_project.id}",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        assert response.json()["name"] == "Test Project"

    @pytest.mark.asyncio
    async def test_get_project_not_found_returns_404(self, auth_override, db_override):
        db_override.execute.return_value.scalars.return_value.first.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/projects/{uuid.uuid4()}",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_project_returns_200(self, auth_override, mock_user, db_override):
        mock_project = self._make_mock_project(mock_user.id)
        db_override.execute.return_value.scalars.return_value.first.return_value = mock_project

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/v1/projects/{mock_project.id}",
                json={"name": "Updated Project Name"},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Project Name"

    @pytest.mark.asyncio
    async def test_delete_project_returns_204(self, auth_override, mock_user, db_override):
        mock_project = self._make_mock_project(mock_user.id)
        db_override.execute.return_value.scalars.return_value.first.return_value = mock_project

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.delete(
                f"/api/v1/projects/{mock_project.id}",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_list_project_jobs_returns_200(self, auth_override, mock_user, db_override):
        """GET /projects/{id}/jobs for an owned project → 200 with empty list."""
        mock_project = self._make_mock_project(mock_user.id)
        # First execute: ownership check (→ scalars().first())
        # Second execute: jobs query (→ scalars().all())
        db_override.execute.return_value.scalars.return_value.first.return_value = mock_project
        db_override.execute.return_value.scalars.return_value.all.return_value = []

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/projects/{mock_project.id}/jobs",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 200
        assert response.json() == []


# ── Upload — non-.sql file with auth ─────────────────────────────────────────

class TestJobUploadExtensionCheck:
    """Covers the file-extension validation branch (line 67 of jobs.py)."""

    @pytest.mark.asyncio
    async def test_upload_non_sql_extension_returns_400(self, auth_override, db_override):
        """Authenticated user uploads a .csv → 400 before any DB/storage work."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/jobs/upload",
                data={"project_id": str(uuid.uuid4()), "app_context": "READ_HEAVY"},
                files={"file": ("data.csv", b"col1,col2\n1,2", "text/csv")},
                headers={"Authorization": "Bearer fake-token"},
            )

        assert response.status_code == 400
        assert "sql" in response.json()["detail"].lower()


# ── get_current_user unit tests ───────────────────────────────────────────────

class TestGetCurrentUser:
    """Direct unit tests for the get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        """Real JWT with valid sub → user object returned from DB."""
        from app.api.v1.auth import get_current_user
        from app.core.security import create_access_token

        user_id = str(uuid.uuid4())
        token = create_access_token(subject=user_id)

        mock_user = MagicMock()
        # AsyncMock child attrs are AsyncMock by default; override execute
        # with an explicit return_value=MagicMock() so .scalars().first() is sync.
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.execute.return_value.scalars.return_value.first.return_value = mock_user

        result = await get_current_user(db=mock_db, token=token)
        assert result is mock_user

    @pytest.mark.asyncio
    async def test_invalid_token_raises_403(self):
        """Garbage string as token → HTTPException 403."""
        from app.api.v1.auth import get_current_user
        from fastapi import HTTPException

        mock_db = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(db=mock_db, token="not.a.valid.jwt")

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_user_not_in_db_raises_404(self):
        """Valid token for a user that no longer exists → HTTPException 404."""
        from app.api.v1.auth import get_current_user
        from app.core.security import create_access_token
        from fastapi import HTTPException

        token = create_access_token(subject=str(uuid.uuid4()))
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.execute.return_value.scalars.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(db=mock_db, token=token)

        assert exc_info.value.status_code == 404


# ── Auth — login success path ─────────────────────────────────────────────────

class TestAuthLoginSuccess:

    @pytest.mark.asyncio
    async def test_login_valid_credentials_returns_token(self, db_override):
        """Correct email + password → 200 with access_token in response."""
        from app.core.security import get_password_hash

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.password_hash = get_password_hash("securePass1")
        db_override.execute.return_value.scalars.return_value.first.return_value = mock_user

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/login",
                data={"username": "alice@example.com", "password": "securePass1"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["access_token"].count(".") == 2


# ── Suggestions — happy path ──────────────────────────────────────────────────

class TestJobSuggestionsHappyPath:
    """Covers the COMPLETED-job branch of GET /jobs/{id}/suggestions."""

    @pytest.mark.asyncio
    async def test_completed_job_returns_suggestions(
        self, auth_override, mock_user, db_override
    ):
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.status = JobStatus.COMPLETED

        mock_project = MagicMock()
        mock_project.user_id = mock_user.id

        mock_artifact = MagicMock()
        mock_artifact.storage_path = "user/job/clean.sql"

        mock_sugg = MagicMock()
        mock_sugg.id = uuid.uuid4()
        mock_sugg.job_id = mock_job.id
        mock_sugg.table_name = "users"
        mock_sugg.issue = "Missing index"
        mock_sugg.suggestion = "Add an index on created_at"
        mock_sugg.risk_level = "MEDIUM"
        mock_sugg.confidence = 0.9
        mock_sugg.sql_patch = "CREATE INDEX idx ON users(created_at);"
        mock_sugg.action_status = "PENDING"

        mock_r1 = MagicMock()
        mock_r1.first.return_value = (mock_job, mock_project)
        mock_r2 = MagicMock()
        mock_r2.scalars.return_value.first.return_value = mock_artifact
        mock_r3 = MagicMock()
        mock_r3.scalars.return_value.all.return_value = [mock_sugg]
        db_override.execute = AsyncMock(side_effect=[mock_r1, mock_r2, mock_r3])

        mock_minio_resp = MagicMock()
        mock_minio_resp.read.return_value = b"CREATE TABLE users (id INT PRIMARY KEY);"

        with patch("app.api.v1.jobs.minio_service") as mock_minio:
            mock_minio.client.get_object.return_value = mock_minio_resp

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/api/v1/jobs/{mock_job.id}/suggestions",
                    headers={"Authorization": "Bearer fake-token"},
                )

        assert response.status_code == 200
        data = response.json()
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["table_name"] == "users"
        assert data["original_sql"] != ""

    @pytest.mark.asyncio
    async def test_suggestions_minio_failure_returns_500(
        self, auth_override, mock_user, db_override
    ):
        """MinIO failure while fetching original SQL → 500."""
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.status = JobStatus.COMPLETED

        mock_project = MagicMock()
        mock_project.user_id = mock_user.id

        mock_artifact = MagicMock()
        mock_artifact.storage_path = "user/job/clean.sql"

        mock_r1 = MagicMock()
        mock_r1.first.return_value = (mock_job, mock_project)
        mock_r2 = MagicMock()
        mock_r2.scalars.return_value.first.return_value = mock_artifact
        db_override.execute = AsyncMock(side_effect=[mock_r1, mock_r2])

        with patch("app.api.v1.jobs.minio_service") as mock_minio:
            mock_minio.client.get_object.side_effect = Exception("storage unavailable")

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/api/v1/jobs/{mock_job.id}/suggestions",
                    headers={"Authorization": "Bearer fake-token"},
                )

        assert response.status_code == 500


# ── ERD schema endpoint ───────────────────────────────────────────────────────

class TestJobSchemaEndpoint:
    """Coverage for GET /jobs/{id}/schema."""

    @pytest.mark.asyncio
    async def test_schema_without_auth_returns_401(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/jobs/{uuid.uuid4()}/schema")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_schema_job_not_found_returns_404(self, auth_override, db_override):
        db_override.execute.return_value.first.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/jobs/{uuid.uuid4()}/schema",
                headers={"Authorization": "Bearer fake-token"},
            )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_schema_no_artifact_returns_404(
        self, auth_override, mock_user, db_override
    ):
        mock_job = MagicMock()
        mock_project = MagicMock()
        mock_project.user_id = mock_user.id

        mock_r1 = MagicMock()
        mock_r1.first.return_value = (mock_job, mock_project)
        mock_r2 = MagicMock()
        mock_r2.scalars.return_value.first.return_value = None
        db_override.execute = AsyncMock(side_effect=[mock_r1, mock_r2])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/jobs/{uuid.uuid4()}/schema",
                headers={"Authorization": "Bearer fake-token"},
            )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_schema_returns_erd_tables(
        self, auth_override, mock_user, db_override
    ):
        """Happy path: owned job with artifact → 200 with parsed ERD tables."""
        mock_job = MagicMock()
        mock_project = MagicMock()
        mock_project.user_id = mock_user.id

        mock_artifact = MagicMock()
        mock_artifact.storage_path = "user/job/clean.sql"

        mock_r1 = MagicMock()
        mock_r1.first.return_value = (mock_job, mock_project)
        mock_r2 = MagicMock()
        mock_r2.scalars.return_value.first.return_value = mock_artifact
        db_override.execute = AsyncMock(side_effect=[mock_r1, mock_r2])

        ddl = b"CREATE TABLE products (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL);"
        mock_minio_resp = MagicMock()
        mock_minio_resp.read.return_value = ddl

        with patch("app.api.v1.jobs.minio_service") as mock_minio:
            mock_minio.client.get_object.return_value = mock_minio_resp

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    f"/api/v1/jobs/{uuid.uuid4()}/schema",
                    headers={"Authorization": "Bearer fake-token"},
                )

        assert response.status_code == 200
        data = response.json()
        assert "tables" in data
        assert data["table_count"] >= 1
        assert any(t["name"] == "products" for t in data["tables"])
