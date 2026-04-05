from fastapi import APIRouter, HTTPException
from app import cache_manager

router = APIRouter()

@router.get("/")
async def list_cache():
    entries = cache_manager.list_cache_entries()
    total_bytes = cache_manager.cache_total_size_bytes()
    return {
        "entries": entries,
        "total_size_bytes": total_bytes,
        "total_size_mb": round(total_bytes / 1024 / 1024, 2),
        "count": len(entries),
    }

@router.delete("/{cache_id}")
async def delete_entry(cache_id: str):
    deleted = cache_manager.delete_cache_entry(cache_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Cache entry not found")
    return {"deleted": cache_id}

@router.delete("/")
async def clear_all():
    count = cache_manager.clear_all_cache()
    return {"cleared": count}
