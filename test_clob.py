import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        # Example token ID from earlier
        res = await client.get("https://clob.polymarket.com/trades?market=115483302436050060330657996514889406855033408384320085942058701641233157973227")
        print(res.status_code)
        print(len(res.json()))
        print(res.json()[:2] if isinstance(res.json(), list) else res.json())

asyncio.run(test())
