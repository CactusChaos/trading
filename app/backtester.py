import os
import subprocess
import csv
import uuid
import base64
import io
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
from app.cache_manager import get_cached_file, store_in_cache

# Temporary directory for poly-trade-scan downloads
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

class Backtester:
    def __init__(self, initial_capital: float = 100.0, fee_rate: float = 0.005):
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate # 0.5% assumed fee for realism requested by user
    
    def fetch_data(self, token_id: str, blocks: int = 5000, start_block: int = None, end_block: int = None):
        # --- Cache check ---
        cached_path = get_cached_file(token_id, start_block, end_block, blocks if start_block is None else None)
        if cached_path:
            return self._parse_csv(cached_path, token_id)

        # --- Download from blockchain ---
        csv_filename = os.path.join(DATA_DIR, f"trades_{uuid.uuid4().hex}.csv")
        try:
            cmd = ["poly", "download"]
            if start_block is not None:
                cmd.extend(["--start", str(start_block)])
            if end_block is not None:
                cmd.extend(["--end", str(end_block)])
            if start_block is None and end_block is None:
                cmd.extend(["-b", str(blocks)])
            cmd.extend(["-o", csv_filename])

            # Inject stable Polygon RPC endpoints
            run_env = os.environ.copy()
            run_env["POLYGON_RPC_URL"] = "https://polygon-bor-rpc.publicnode.com"
            run_env["POLYGON_WSS_URL"] = "wss://polygon-bor-rpc.publicnode.com"

            # Run poly with a hard 5-minute timeout.
            # If the RPC endpoint hangs, subprocess.TimeoutExpired is raised
            # and caught below as a RuntimeError, unblocking the request.
            subprocess.run(
                cmd, env=run_env, check=True,
                capture_output=True, text=True, timeout=300
            )

            # --- Parse, store in cache, clean up temp file ---
            result = self._parse_csv(csv_filename, token_id)
            store_in_cache(
                token_id=token_id,
                start_block=start_block,
                end_block=end_block,
                blocks=blocks if start_block is None else None,
                source_csv=csv_filename,
                row_count=len(result["prices"]),
            )
            return result

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"poly-trade-scan failed: {e.stderr}")
        finally:
            if os.path.exists(csv_filename):
                os.remove(csv_filename)

    def _parse_csv(self, csv_filename: str, token_id: str) -> dict:
        """Parse a trade CSV and filter rows matching token_id."""
        prices = []
        volumes = []
        timestamps = []
        with open(csv_filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['token_id'] == token_id:
                    try:
                        prices.append(float(row['price']))
                        volumes.append(float(row['tokens']))
                        timestamps.append(row['timestamp'])
                    except (ValueError, KeyError):
                        continue
        return {
            "prices": np.array(prices, dtype=float),
            "volumes": np.array(volumes, dtype=float),
            "timestamps": timestamps,
        }

    def execute_model(self, model_code: str, prices: np.ndarray, volumes: np.ndarray) -> np.ndarray:
        # Create a restricted execution environment
        namespace = {
            'np': np,
            'prices': prices,
            'volumes': volumes,
            'signals': np.zeros_like(prices)
        }
        # Run user code
        exec(model_code, namespace)
        
        # User code must define a function `model(prices, volumes)` and return signals
        if 'model' in namespace and callable(namespace['model']):
            signals = namespace['model'](prices, volumes)
        else:
            raise ValueError("Model code must define a 'model(prices, volumes)' function.")
        
        return signals

    def run_backtest(self, prices: np.ndarray, signals: np.ndarray):
        # Simple backtest loop covering fees
        capital = self.initial_capital
        position_shares = 0.0
        equity_curve = []
        trades = []
        
        for i in range(len(prices)):
            price = prices[i]
            signal = signals[i] if i < len(signals) else 0
            
            # Execute trade based on signal
            # signal = 1 (Buy max), -1 (Sell all), 0 (Hold)
            
            trade_executed = False
            trade_type = ""
            cost = 0.0
            
            if signal > 0 and capital > 0: # Buy
                # Buy as much as possible at current price
                # Cost includes fee
                # shares * price * (1 + fee) = capital
                shares_to_buy = capital / (price * (1 + self.fee_rate))
                cost = shares_to_buy * price * (1 + self.fee_rate)
                fee = shares_to_buy * price * self.fee_rate
                
                position_shares += shares_to_buy
                capital -= cost
                trade_executed = True
                trade_type = "BUY"
                
            elif signal < 0 and position_shares > 0: # Sell
                # Sell all shares
                revenue = position_shares * price
                fee = revenue * self.fee_rate
                capital += (revenue - fee)
                
                cost = revenue - fee
                position_shares = 0.0
                trade_executed = True
                trade_type = "SELL"
                
            # Current value of portfolio
            current_equity = capital + (position_shares * price * (1 - self.fee_rate)) # liquidation value
            equity_curve.append(current_equity)
            
            if trade_executed:
                trades.append({
                    "step": i,
                    "type": trade_type,
                    "price": price,
                    "equity": current_equity,
                    "capital": capital,
                    "position": position_shares
                })
        
        equity_arr = np.array(equity_curve)
        
        # Analytics
        if len(equity_arr) > 0:
            total_return = (equity_arr[-1] - self.initial_capital) / self.initial_capital
            running_max = np.maximum.accumulate(equity_arr)
            drawdowns = (running_max - equity_arr) / running_max
            max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0
            
            # Approximation of Sharpe Ratio (ignoring risk-free rate, daily conversion)
            returns = np.diff(equity_arr) / equity_arr[:-1]
            if len(returns) > 1 and np.std(returns) > 0:
                sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(len(prices))
            else:
                sharpe = 0.0
        else:
            total_return = 0.0
            max_drawdown = 0.0
            sharpe = 0.0
            
        return {
            "initial_capital": self.initial_capital,
            "final_equity": equity_arr[-1] if len(equity_arr) > 0 else self.initial_capital,
            "total_return_pct": total_return * 100,
            "max_drawdown_pct": max_drawdown * 100,
            "sharpe_ratio": sharpe,
            "trades": len(trades),
            "trade_log": trades,
            "equity_curve": equity_curve
        }

    def generate_chart(self, prices: np.ndarray, equity_curve: list, timestamps: list) -> str:
        if len(prices) == 0:
            return ""

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True, gridspec_kw={'height_ratios': [3, 2]})
        
        # Plot Prices
        ax1.plot(prices, label="Price", color="#00f2fe")
        ax1.set_title("Market Price")
        ax1.set_ylabel("Price")
        ax1.grid(True, linestyle="--", alpha=0.5)
        ax1.legend()
        
        # Plot Equity
        ax2.plot(equity_curve, label="Portfolio Value", color="#4facfe")
        ax2.set_title("Strategy Equity Curve")
        ax2.set_ylabel("Value ($)")
        ax2.grid(True, linestyle="--", alpha=0.5)
        ax2.legend()
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100, facecolor='#111827')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        
        return img_str
