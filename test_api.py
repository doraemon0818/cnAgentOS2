import requests, json

# Test top/rank API
url_top = "https://api.52vmy.cn/api/music/wy/top"
params_top = {"t": 4, "n": 3}

r = requests.get(url_top, params=params_top, timeout=15)
data = r.json()
print("=== TOP API raw data ===")
print(json.dumps(data, ensure_ascii=False, indent=2)[:1500])
print("\n...")

# Also check if there's a picUrl in the data
if isinstance(data, dict):
    d = data.get("data", data)
    if isinstance(d, list) and len(d) > 0:
        print("\nFirst item keys:", list(d[0].keys()))
        item = d[0]
        for k in ['cover', 'pic', 'picUrl', 'image', 'album', 'img']:
            if k in item:
                print(f"  {k}: {item[k]}")