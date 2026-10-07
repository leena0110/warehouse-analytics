"""
storage_service.py — Cloud file storage abstraction.

In LOCAL mode:   files are saved to ./uploads/<container>/ directory.
In AZURE mode:   files are uploaded to Azure Blob Storage.

The service returns a uniform result dict regardless of storage backend.
Frontend/backend never need to know which backend is active.
"""

import os
import uuid
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, BinaryIO

from app.core.config import get_settings
from app.core.logger import logger, log_event

settings = get_settings()

# Local fallback upload directory
LOCAL_UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class StorageResult:
    def __init__(self, success: bool, blob_name: str, url: str, mode: str, error: str = ""):
        self.success = success
        self.blob_name = blob_name
        self.url = url
        self.mode = mode          # "azure" | "local"
        self.error = error


async def upload_file(file_content: bytes, original_filename: str) -> StorageResult:
    """
    Upload a file to Azure Blob Storage (production) or local filesystem (dev).
    Returns a StorageResult with blob name and URL.
    """
    ext = Path(original_filename).suffix.lower()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    blob_name = f"datasets/{timestamp}_{unique_id}{ext}"

    if settings.is_azure_storage_enabled:
        return await _upload_to_azure(file_content, blob_name, original_filename)
    else:
        return await _upload_to_local(file_content, blob_name, original_filename)


async def _upload_to_azure(file_content: bytes, blob_name: str, original_filename: str) -> StorageResult:
    """Upload to Azure Blob Storage."""
    try:
        from azure.storage.blob import BlobServiceClient, ContentSettings
        blob_service = BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
        container_client = blob_service.get_container_client(settings.azure_storage_container_name)

        # Ensure container exists
        try:
            container_client.create_container()
        except Exception:
            pass  # Already exists

        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(
            file_content,
            overwrite=True,
            content_settings=ContentSettings(content_type="text/csv"),
        )

        url = blob_client.url
        log_event("blob_upload_success", details=f"blob={blob_name} size={len(file_content)}")
        return StorageResult(success=True, blob_name=blob_name, url=url, mode="azure")

    except Exception as exc:
        logger.error(f"Azure Blob upload failed: {exc}")
        # Fallback to local on error
        logger.warning("Falling back to local storage after Azure error.")
        return await _upload_to_local(file_content, blob_name, original_filename)


async def _upload_to_local(file_content: bytes, blob_name: str, original_filename: str) -> StorageResult:
    """Save file to local filesystem (development fallback)."""
    try:
        dest_path = LOCAL_UPLOAD_DIR / blob_name.replace("/", os.sep)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(file_content)

        url = f"local://{dest_path}"
        log_event("local_upload_success", details=f"path={dest_path} size={len(file_content)}")
        return StorageResult(success=True, blob_name=blob_name, url=url, mode="local")

    except Exception as exc:
        logger.error(f"Local file save failed: {exc}")
        return StorageResult(success=False, blob_name="", url="", mode="local", error=str(exc))


async def download_file(blob_name: str) -> Optional[bytes]:
    """Download a file from Azure Blob Storage or local filesystem."""
    if settings.is_azure_storage_enabled:
        try:
            from azure.storage.blob import BlobServiceClient
            blob_service = BlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string
            )
            blob_client = blob_service.get_container_client(
                settings.azure_storage_container_name
            ).get_blob_client(blob_name)
            return blob_client.download_blob().readall()
        except Exception as exc:
            logger.error(f"Azure Blob download failed: {exc}")
            return None
    else:
        local_path = LOCAL_UPLOAD_DIR / blob_name.replace("/", os.sep)
        if local_path.exists():
            return local_path.read_bytes()
        return None


async def list_blobs(prefix: str = "datasets/") -> list:
    """List blobs in container matching prefix."""
    if settings.is_azure_storage_enabled:
        try:
            from azure.storage.blob import BlobServiceClient
            blob_service = BlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string
            )
            container_client = blob_service.get_container_client(
                settings.azure_storage_container_name
            )
            return [b.name for b in container_client.list_blobs(name_starts_with=prefix)]
        except Exception as exc:
            logger.error(f"Azure list blobs failed: {exc}")
            return []
    else:
        local_dir = LOCAL_UPLOAD_DIR / "datasets"
        if local_dir.exists():
            return [str(f.relative_to(LOCAL_UPLOAD_DIR)) for f in local_dir.rglob("*") if f.is_file()]
        return []


async def delete_blob(blob_name: str) -> bool:
    """Delete a blob from storage (admin only)."""
    if settings.is_azure_storage_enabled:
        try:
            from azure.storage.blob import BlobServiceClient
            blob_service = BlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string
            )
            blob_client = blob_service.get_container_client(
                settings.azure_storage_container_name
            ).get_blob_client(blob_name)
            blob_client.delete_blob()
            return True
        except Exception as exc:
            logger.error(f"Azure delete blob failed: {exc}")
            return False
    else:
        local_path = LOCAL_UPLOAD_DIR / blob_name.replace("/", os.sep)
        if local_path.exists():
            local_path.unlink()
            return True
        return False
