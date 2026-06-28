import httpx
import json

def test():
    ip = "192.168.2.109"
    port = 30800
    url = f"http://{ip}:{port}/api/tags"
    print(f"Checking {url}...")
    try:
        resp = httpx.get(url, timeout=5.0)
        print(f"Success from {url}!")
        print(json.dumps(resp.json(), indent=2))
    except Exception as e:
        print(f"Failed for {url}: {e}")

if __name__ == "__main__":
    test()
