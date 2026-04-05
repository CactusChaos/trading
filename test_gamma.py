import httpx
import json
import asyncio

async def main():
    url = 'https://gamma-api.polymarket.com/events'
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params={"title": "election"})
        events = resp.json()
        if events and 'markets' in events[0]:
            print(json.dumps(events[0]['markets'][0], indent=2))

asyncio.run(main())
