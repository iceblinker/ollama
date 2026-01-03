import requests

try:
    data = requests.get('http://vixsrc-addon:3000/manifest.json').json()
    catalog = data['catalogs'][0]
    print(f"ID: {catalog['id']}")
    print(f"Type: {catalog['type']}")
    print(f"URL Hint: /catalog/{catalog['type']}/{catalog['id']}.json")
except Exception as e:
    print(e)
