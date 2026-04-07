"""
Cache manager for poly-trade-scan downloads.
Stores CSV trade data keyed by (token_id, start_block, end_block).
"""
import os
import json
import hashlib
import time
import shutil
from dataclasses import dataclass, asdict
from typing import Optional

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")
CACHE_INDEX_FILE = os.path.join(CACHE_DIR, "index.json")

os.makedirs(CACHE_DIR, exist_ok=True)


@dataclass
class CacheEntry:
    cache_id: str
    token_id: str
    start_block: Optional[int]
    end_block: Optional[int]
    blocks: Optional[int]        # if fetched by block count
    file_path: str
    file_size_bytes: int
    created_at: float            # unix timestamp
    last_accessed: float         # unix timestamp
    row_count: int               # number of trades in file


def _make_cache_id(start_block: Optional[int], end_block: Optional[int], blocks: Optional[int]) -> str:
    """Create a stable cache key from fetch parameters, agnostic of token."""
    key = f"{start_block}:{end_block}:{blocks}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _load_index() -> dict[str, dict]:
    if not os.path.exists(CACHE_INDEX_FILE):
        return {}
    try:
        with open(CACHE_INDEX_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_index(index: dict[str, dict]) -> None:
    with open(CACHE_INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)


def get_cached_file(start_block: Optional[int], end_block: Optional[int], blocks: Optional[int]) -> Optional[str]:
    """
    Returns the path to a cached CSV file if it exists, otherwise None.
    Updates last_accessed timestamp on hit.
    """
    # 1. Exact match
    cache_id = _make_cache_id(start_block, end_block, blocks)
    index = _load_index()
    entry_data = index.get(cache_id)

    # 2. Superset match (if explicit bounds)
    if not entry_data and start_block is not None and end_block is not None:
        for cid, data in index.items():
            entry_start = data.get("start_block")
            entry_end = data.get("end_block")
            if entry_start is not None and entry_end is not None:
                if entry_start <= start_block and entry_end >= end_block:
                    entry_data = data
                    cache_id = cid
                    break

    if not entry_data:
        return None

    file_path = entry_data["file_path"]
    if not os.path.exists(file_path):
        # Stale index entry — clean it up
        del index[cache_id]
        _save_index(index)
        return None

    # Update last accessed
    entry_data["last_accessed"] = time.time()
    _save_index(index)
    return file_path


def store_in_cache(
    token_id: str,
    start_block: Optional[int],
    end_block: Optional[int],
    blocks: Optional[int],
    source_csv: str,
    row_count: int,
) -> str:
    """
    Copy a downloaded CSV into the cache directory and record it in the index.
    Returns the cached file path.
    """
    cache_id = _make_cache_id(start_block, end_block, blocks)
    cached_path = os.path.join(CACHE_DIR, f"{cache_id}.csv")

    shutil.copy2(source_csv, cached_path)
    file_size = os.path.getsize(cached_path)
    now = time.time()

    entry = CacheEntry(
        cache_id=cache_id,
        token_id=token_id,
        start_block=start_block,
        end_block=end_block,
        blocks=blocks,
        file_path=cached_path,
        file_size_bytes=file_size,
        created_at=now,
        last_accessed=now,
        row_count=row_count,
    )

    index = _load_index()
    index[cache_id] = asdict(entry)
    _save_index(index)
    return cached_path


def list_cache_entries() -> list[dict]:
    """Return all cache entries with human-readable metadata."""
    index = _load_index()
    entries = []
    for cache_id, data in index.items():
        # Verify file still exists
        if os.path.exists(data.get("file_path", "")):
            entries.append(data)
    # Sort newest first
    entries.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return entries


def delete_cache_entry(cache_id: str) -> bool:
    """Delete a specific cache entry. Returns True if deleted."""
    index = _load_index()
    entry = index.get(cache_id)
    if not entry:
        return False

    file_path = entry.get("file_path", "")
    if os.path.exists(file_path):
        os.remove(file_path)

    del index[cache_id]
    _save_index(index)
    return True


def clear_all_cache() -> int:
    """Delete all cached files. Returns number of entries deleted."""
    index = _load_index()
    count = 0
    for cache_id, entry in index.items():
        file_path = entry.get("file_path", "")
        if os.path.exists(file_path):
            os.remove(file_path)
            count += 1

    _save_index({})
    return count


def cache_total_size_bytes() -> int:
    """Return total size of all cached files in bytes."""
    index = _load_index()
    total = 0
    for entry in index.values():
        fp = entry.get("file_path", "")
        if os.path.exists(fp):
            total += os.path.getsize(fp)
    return total
