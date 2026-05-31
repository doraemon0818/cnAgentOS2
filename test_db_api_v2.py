import requests
import json

session = requests.Session()

try:
    print("Step 1: Getting XSRF token...")
    resp = session.get('http://localhost:10086/admin/database')
    print(f"Status: {resp.status_code}")
    
    xsrf_token = ''
    for cookie in session.cookies:
        if cookie.name == '_xsrf':
            xsrf_token = cookie.value
            break
    
    print(f"XSRF Token: {xsrf_token}")
    
    print("\nStep 2: Testing database connection...")
    url = 'http://localhost:10086/api/database/test'
    data = {
        'type': 'mysql',
        'mysql': {
            'host': 'localhost',
            'port': 3306,
            'user': 'root',
            'password': '912419',
            'database': 'cnagentos',
            'charset': 'utf8mb4'
        },
        '_xsrf': xsrf_token
    }
    
    json_str = json.dumps(data)
    print(f"JSON body (first 100 chars): {json_str[:100]}")
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    resp = session.post(url, data=json_str, headers=headers)
    print(f"\nStatus Code: {resp.status_code}")
    
    if resp.status_code == 200:
        result = resp.json()
        print(f"Success! Response: {result}")
    else:
        print(f"Response Body: {resp.text}")
    
except Exception as e:
    import traceback
    print(f"Error: {type(e).__name__}: {e}")
    traceback.print_exc()
