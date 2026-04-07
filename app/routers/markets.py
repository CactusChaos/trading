from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter()
GAMMA_API_URL = "https://gamma-api.polymarket.com"

@router.get("/search")
async def search_markets(q: str):
    async with httpx.AsyncClient() as client:
        try:
            # Polymarket Gamma API title search or slug search, we fetch recent events without active filter constraints
            resp = await client.get(f"{GAMMA_API_URL}/public-search", params={"q": q})
            if resp.status_code == 200:
                data = resp.json()
                events = data.get("events", [])
                filtered = []
                for e in events:
                    # Only keep events that have at least one valid CLOB market
                    if "markets" in e and any(m.get("clobTokenIds") for m in e["markets"]):
                        filtered.append(e)
                return filtered
            return []
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/{market_slug}")
async def get_market(market_slug: str):
    async with httpx.AsyncClient() as client:
        # First try as event
        resp = await client.get(f"{GAMMA_API_URL}/events", params={"slug": market_slug})
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                event = data[0]
                if "markets" in event and event["markets"]:
                    # Return the first market in the event that has CLOB tokens
                    for m in event["markets"]:
                        if m.get("clobTokenIds"):
                            return m
                    # fallback
                    return event["markets"][0]
                return event
        
        # Fallback to single market
        resp = await client.get(f"{GAMMA_API_URL}/markets", params={"slug": market_slug})
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Market not found")
        data = resp.json()
        if not data:
            raise HTTPException(status_code=404, detail="Market not found")
        return data[0]
