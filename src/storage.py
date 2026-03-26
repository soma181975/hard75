"""S3/MinIO storage client for photo uploads."""

import io
import uuid
from datetime import datetime
from typing import BinaryIO, Optional

import boto3
from botocore.config import Config

from src.config import get_settings


class StorageClient:
    """S3-compatible storage client for MinIO/S3."""

    def __init__(self):
        settings = get_settings()
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4"),
        )
        self._bucket = settings.s3_bucket
        self._endpoint = settings.s3_endpoint

    def upload_file(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str = "image/jpeg",
        folder: str = "photos",
    ) -> str:
        """
        Upload a file to storage.

        Returns the public URL of the uploaded file.
        """
        # Generate unique filename
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "jpg"
        unique_name = f"{folder}/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4()}.{ext}"

        self._client.upload_fileobj(
            file,
            self._bucket,
            unique_name,
            ExtraArgs={"ContentType": content_type},
        )

        # Return the public URL
        return f"{self._endpoint}/{self._bucket}/{unique_name}"

    def upload_bytes(
        self,
        data: bytes,
        filename: str,
        content_type: str = "image/jpeg",
        folder: str = "photos",
    ) -> str:
        """Upload bytes data to storage."""
        return self.upload_file(
            io.BytesIO(data),
            filename,
            content_type,
            folder,
        )

    def delete_file(self, url: str) -> bool:
        """Delete a file from storage."""
        try:
            # Extract key from URL
            key = url.split(f"{self._bucket}/")[-1]
            self._client.delete_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Get a presigned URL for temporary access."""
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def list_files(self, prefix: str = "") -> list[dict]:
        """List files in a folder."""
        response = self._client.list_objects_v2(
            Bucket=self._bucket,
            Prefix=prefix,
        )
        return [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"],
            }
            for obj in response.get("Contents", [])
        ]


# Global storage instance
storage = StorageClient()


def get_storage() -> StorageClient:
    """Dependency for getting storage instance."""
    return storage
