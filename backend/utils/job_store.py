import json
import os
from typing import Any, Dict, Optional

import redis
from redis.exceptions import RedisError

import config

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
JOB_TTL_SECONDS = int(os.getenv('JOB_TTL_SECONDS', 7 * 24 * 60 * 60))


def _init_redis_client() -> Optional[redis.Redis]:
    """Initialize Redis client and validate connectivity."""
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=2,
        )
        client.ping()
        print(f"[Redis] Connected to {REDIS_HOST}:{REDIS_PORT} (db={REDIS_DB})")
        return client
    except RedisError as exc:
        print(
            f"[Redis] 无法连接到 {REDIS_HOST}:{REDIS_PORT}，"
            f"将使用内存存储 (Phase 1 fallback)。原因: {exc}"
        )
        return None


redis_client = _init_redis_client()
REDIS_AVAILABLE = redis_client is not None


def get_job_key(job_id: str) -> str:
    """Return the canonical Redis key for a job."""
    return f"job:{job_id}"


def _serialize(job_data: Dict[str, Any]) -> str:
    return json.dumps(job_data, ensure_ascii=False)


def _deserialize(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("[Redis] 警告: 任务数据解析失败，内容已损坏。")
        return None


def save_job(job_id: str, job_data: Dict[str, Any], ttl_seconds: Optional[int] = JOB_TTL_SECONDS) -> None:
    """Persist job data to Redis or fallback to in-memory storage."""
    if redis_client:
        key = get_job_key(job_id)
        payload = _serialize(job_data)
        if ttl_seconds:
            redis_client.setex(key, ttl_seconds, payload)
        else:
            redis_client.set(key, payload)
    else:
        config.jobs_storage[job_id] = job_data


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Load job data from Redis or fallback storage."""
    if redis_client:
        return _deserialize(redis_client.get(get_job_key(job_id)))
    return config.jobs_storage.get(job_id)


def delete_job(job_id: str) -> None:
    """Remove job data from storage."""
    if redis_client:
        redis_client.delete(get_job_key(job_id))
    else:
        config.jobs_storage.pop(job_id, None)


__all__ = [
    "JOB_TTL_SECONDS",
    "REDIS_AVAILABLE",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_DB",
    "delete_job",
    "get_job",
    "get_job_key",
    "redis_client",
    "save_job",
]
