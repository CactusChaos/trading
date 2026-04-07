import requests

rpcs = [
    "https://polygon.drpc.org",
    "https://polygon-rpc.com",
    "https://rpc-mainnet.maticvigil.com",
    "https://polygon-bor-rpc.publicnode.com"
]

for r in rpcs:
    try:
        res = requests.post(r, json={"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}, timeout=5)
        print(f"{r}: {res.status_code} {res.json()}")
    except Exception as e:
        print(f"{r}: ERROR {e}")
