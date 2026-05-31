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
    
    print(f"XSRF Token from cookie: {xsrf_token}")
    
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
    
    print(f"Sending _xsrf in body: {data['_xsrf'][:20]}...")
    
    headers = {
        'Content-Type': 'application/json',
        'X-Xsrftoken': xsrf_token,
        'X-Csrftoken': xsrf_token
    }
    
    print(f"Sending X-Xsrftoken header: {headers['X-Xsrftoken'][:20]}...")
    
    resp = session.post(url, json=data, headers=headers)
    print(f"\nStatus Code: {resp.status_code}")
    print(f"Response Body: {resp.text[:500] if len(resp.text) > 500 else resp.text}")
    
except Exception as e:
    import traceback
    print(f"Error: {type(e).__name__}: {e}")
    traceback.print_exc()
