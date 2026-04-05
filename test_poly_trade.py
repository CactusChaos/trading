from app.backtester import Backtester
import traceback

def main():
    try:
        bt = Backtester(initial_capital=100.0)
        # Using a reliable token ID and small block range
        # Let's see what fetch_data does
        data = bt.fetch_data("28182404005967940652495463228537840901055649726248190462854914416579180110833", blocks=100)
        print("Success! Trades fetched:", len(data["prices"]))
    except Exception as e:
        print("Error:")
        traceback.print_exc()

main()
