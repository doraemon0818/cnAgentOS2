import requests
import json

try:
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
        }
    }
    
    resp = requests.post(url, json=data)
    print('Status:', resp.status_code)
    print('Response:', resp.text)
except Exception as e:
    print('Error:', str(e))
