import requests
from bs4 import BeautifulSoup

headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nutrition-charts.com/',
}
url='https://www.nutrition-charts.com/?s=jimmy+johns'
resp=requests.get(url, headers=headers, timeout=10)
soup=BeautifulSoup(resp.text, 'html.parser')
results=soup.select('.entry-title a')
for a in results:
    print(a.get_text(strip=True), a.get('href'))
