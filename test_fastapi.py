import urllib.request
try:
    print(urllib.request.urlopen("http://localhost:8000/").read().decode())
except urllib.error.HTTPError as e:
    print(e.read().decode())
