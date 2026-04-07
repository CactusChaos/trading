import time
from concurrent.futures import ThreadPoolExecutor
import requests

def test_pool(pool_size):
    s = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
    s.mount("https://", adapter)
    
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}
    
    def fetch(_):
        return s.post("https://polygon.drpc.org", json=payload).status_code
        
    start = time.time()
    with ThreadPoolExecutor(max_workers=40) as e:
        list(e.map(fetch, range(200)))
    print(f"Pool size {pool_size}: {time.time() - start:.2f}s")

test_pool(10)
test_pool(100)
