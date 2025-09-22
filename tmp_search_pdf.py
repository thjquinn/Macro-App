import re
import requests

headers={'User-Agent':'Mozilla/5.0'}
resp=requests.get('https://duckduckgo.com/html/?q=jimmy%20johns%20nutrition%20pdf', headers=headers, timeout=10)
print(resp.status_code)
matches=re.findall(r'https?://[^"\']+\.pdf', resp.text)
print(matches[:5])
