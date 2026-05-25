import urllib.request
import json

# 测试词云API
url = "http://localhost:10086/admin/api/data/screen?action=wordcloud&limit=20"

try:
    req = urllib.request.Request(url)
    # 需要登录cookie，这里先测试连接
    response = urllib.request.urlopen(req, timeout=5)
    data = json.loads(response.read().decode('utf-8'))
    print("API Response:")
    print(json.dumps(data, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"Error: {e}")
    print("Note: API requires authentication. This is expected if not logged in.")
