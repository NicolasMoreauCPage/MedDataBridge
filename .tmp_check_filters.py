import urllib.request
url = 'http://127.0.0.1:8000/patients?name=foo&gender=male'
with urllib.request.urlopen(url) as resp:
	body = resp.read().decode('utf-8', errors='replace')
	print(resp.status)
	print(body[:4000])
