import io
import datetime
import logging
from minio import Minio
from minio.error import S3Error
from app.core.config import settings

logger = logging.getLogger(__name__)


class MinioService:
    def __init__(self):
        # Lazy initialization: the client is created on first use, not at module
        # import time. This allows the application to start even if MinIO is not
        # yet available (e.g., during container startup sequencing).
        self._client: Minio | None = None

    @property
    def client(self) -> Minio:
        """Lazy-initialized Minio client."""
        if self._client is None:
            self._client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=False,  # Local MinIO uses HTTP
            )
        return self._client

    def ensure_bucket_exists(self) -> None:
        """
        Create the storage bucket if it does not already exist.
        Called explicitly during app startup — not at import time.
        """
        try:
            if not self.client.bucket_exists(settings.MINIO_BUCKET_NAME):
                self.client.make_bucket(settings.MINIO_BUCKET_NAME)
                logger.info(f"MinIO bucket '{settings.MINIO_BUCKET_NAME}' created.")
            else:
                logger.info(f"MinIO bucket '{settings.MINIO_BUCKET_NAME}' already exists.")
        except S3Error as e:
            logger.error(f"MinIO bucket check/create error: {e}")
            raise

    def upload_file(
        self,
        file_data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes to MinIO. Returns the object_name on success."""
        try:
            self.client.put_object(
                settings.MINIO_BUCKET_NAME,
                object_name,
                io.BytesIO(file_data),
                len(file_data),
                content_type=content_type,
            )
            logger.info(f"Uploaded '{object_name}' to MinIO bucket '{settings.MINIO_BUCKET_NAME}'.")
            return object_name
        except S3Error as e:
            logger.error(f"MinIO upload error for '{object_name}': {e}")
            raise

    def get_presigned_url(self, object_name: str, expires_hours: int = 1) -> str | None:
        """
        Generate a presigned GET URL valid for `expires_hours` hours.
        Returns None on failure (caller should handle gracefully).
        """
        try:
            url = self.client.presigned_get_object(
                settings.MINIO_BUCKET_NAME,
                object_name,
                expires=datetime.timedelta(hours=expires_hours),
            )
            return url
        except Exception as e:
            logger.error(f"MinIO presigned URL error for '{object_name}': {e}")
            return None


# Module-level singleton — lazy init, safe to import
minio_service = MinioService()
