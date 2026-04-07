import asyncio
from app.backtester import Backtester

async def main():
    bt = Backtester(initial_capital=100.0)
    data = bt.fetch_data("115483302436050060330657996514889406855033408384320085942058701641233157973227", blocks=100)
    print("Success! Trades fetched:", len(data["prices"]))

asyncio.run(main())
