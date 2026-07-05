import boto3
from botocore.config import Config
from core.config import settings
import logging
from typing import Dict, Optional
import os

logger = logging.getLogger(__name__)

_r2_client = None


def _get_r2_client():
    global _r2_client
    if _r2_client is None:
        _r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto"
        )
    return _r2_client


def generate_presigned_upload_url(key: str, content_type: str, expiration: int = 3600) -> Dict[str, str]:
    client = _get_r2_client()
    
    response = client.generate_presigned_post(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 0, settings.max_video_size_mb * 1024 * 1024]
        ],
        ExpiresIn=expiration
    )
    
    return {
        "url": response["url"],
        "fields": response["fields"]
    }


def generate_presigned_download_url(key: str, expiration: int = 3600) -> str:
    client = _get_r2_client()
    
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": key},
        ExpiresIn=expiration
    )
    
    return url


def upload_to_r2(key: str, data: bytes, content_type: str) -> bool:
    client = _get_r2_client()
    
    try:
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type
        )
        return True
    except Exception as e:
        logger.error(f"R2 upload error: {e}")
        return False


def download_from_r2(key: str) -> Optional[bytes]:
    client = _get_r2_client()
    
    try:
        response = client.get_object(Bucket=settings.r2_bucket_name, Key=key)
        return response["Body"].read()
    except Exception as e:
        logger.error(f"R2 download error: {e}")
        return None


def delete_from_r2(key: str) -> bool:
    client = _get_r2_client()
    
    try:
        client.delete_object(Bucket=settings.r2_bucket_name, Key=key)
        return True
    except Exception as e:
        logger.error(f"R2 delete error: {e}")
        return False


def get_public_url(key: str) -> str:
    return f"{settings.r2_public_url}/{key}"