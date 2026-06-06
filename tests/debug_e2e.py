import subprocess
import json

def test():
    cmd = [
        "curl", "-s", 
        "-H", "Authorization: Bearer TestUser c0a81a4b-115a-4eb6-bc2c-40908c58bf64",
        "http://127.0.0.1:3000/aggregate-status"
    ]
    out = subprocess.check_output(cmd).decode()
    print(f"RAW OUTPUT: {out}")
    data = json.loads(out)
    print(f"JSON DATA: {data}")

if __name__ == "__main__":
    test()
