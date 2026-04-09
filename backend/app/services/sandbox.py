import io
import tarfile
import uuid
import time
import logging

import docker
from docker.errors import DockerException

logger = logging.getLogger(__name__)

# Maximum time (seconds) to wait for sandbox container before aborting.
# Prevents hanging workers. Rule from 02-dos-and-donts.md: 30s max.
SANDBOX_TIMEOUT_SECONDS = 30
# How long to wait between pg_isready checks (seconds)
DB_READY_POLL_INTERVAL = 2
# Max retries for pg_isready (total wait = retries × interval)
DB_READY_MAX_RETRIES = 10


class SandboxService:
    def __init__(self):
        # Lazy initialization: deferred until first use to avoid crashing at
        # import time when the Docker socket is not available (e.g., in tests).
        self._client: docker.DockerClient | None = None

    @property
    def client(self) -> docker.DockerClient | None:
        if self._client is None:
            try:
                self._client = docker.from_env()
                logger.info("Docker client initialized successfully.")
            except DockerException as e:
                logger.error(f"Failed to initialize Docker client: {e}")
                self._client = None
        return self._client

    def run_sql_validation(self, sql_content: str, db_dialect: str = "postgresql") -> dict:
        """
        Spins up a temporary Docker container, runs the SQL as a dry-run,
        captures the result, and tears down the container.

        Returns: {'success': bool, 'logs': str}

        A global deadline of SANDBOX_TIMEOUT_SECONDS is enforced to prevent
        the Celery worker from hanging if the container never becomes ready.
        """
        if not self.client:
            return {
                "success": False,
                "logs": "Docker client not available. Check if Docker socket is mounted.",
            }

        # Select container image based on dialect
        image = "postgres:15-alpine"
        if "mysql" in db_dialect.lower():
            image = "mysql:8"

        container_name = f"sandbox_{uuid.uuid4().hex[:8]}"
        container = None
        start_time = time.monotonic()

        try:
            # ── 1. Start ephemeral container ────────────────────────────────
            logger.info(f"Starting sandbox container '{container_name}' ({image})...")
            container = self.client.containers.run(
                image,
                name=container_name,
                environment={"POSTGRES_PASSWORD": "root"},
                detach=True,
                network_disabled=True,  # No network needed for pure SQL validation
                mem_limit="256m",       # Cap memory usage
            )

            # ── 2. Wait for DB to be ready (with global timeout) ────────────
            retries = DB_READY_MAX_RETRIES
            is_ready = False

            while retries > 0:
                # Check global timeout
                elapsed = time.monotonic() - start_time
                if elapsed >= SANDBOX_TIMEOUT_SECONDS:
                    logger.warning(f"Sandbox timeout after {elapsed:.1f}s waiting for DB ready.")
                    return {"success": False, "logs": f"Sandbox timeout: DB not ready after {SANDBOX_TIMEOUT_SECONDS}s."}

                time.sleep(DB_READY_POLL_INTERVAL)
                exit_code, _ = container.exec_run("pg_isready -U postgres")
                if exit_code == 0:
                    is_ready = True
                    break
                retries -= 1

            if not is_ready:
                return {"success": False, "logs": "Database container failed to become ready."}

            # ── 3. Copy SQL file into container using tar archive ───────────
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                data = sql_content.encode("utf-8")
                tarinfo = tarfile.TarInfo(name="validate.sql")
                tarinfo.size = len(data)
                tar.addfile(tarinfo, io.BytesIO(data))
            tar_stream.seek(0)
            container.put_archive("/tmp", tar_stream)

            # ── 4. Check global timeout before running SQL ──────────────────
            elapsed = time.monotonic() - start_time
            if elapsed >= SANDBOX_TIMEOUT_SECONDS:
                return {"success": False, "logs": f"Sandbox timeout before SQL execution: {elapsed:.1f}s elapsed."}

            # ── 5. Execute SQL via psql ─────────────────────────────────────
            exec_result = container.exec_run(
                "psql -U postgres -d postgres -f /tmp/validate.sql",
                stdout=True,
                stderr=True,
            )
            exit_code = exec_result.exit_code
            output = exec_result.output.decode("utf-8", errors="replace")

            logger.info(f"Sandbox exec exit_code={exit_code} for container '{container_name}'")

            return {"success": exit_code == 0, "logs": output}

        except Exception as e:
            logger.error(f"Sandbox unexpected error for '{container_name}': {e}")
            return {"success": False, "logs": f"Sandbox error: {str(e)}"}

        finally:
            # ── 6. Always cleanup container ─────────────────────────────────
            if container:
                try:
                    container.stop(timeout=5)
                    container.remove(force=True)
                    logger.info(f"Sandbox container '{container_name}' cleaned up.")
                except Exception as e:
                    logger.warning(f"Failed to cleanup container '{container_name}': {e}")


# Module-level singleton — lazy Docker init, safe to import
sandbox_service = SandboxService()
