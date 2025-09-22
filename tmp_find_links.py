import requests
from bs4 import BeautifulSoup

headers={'User-Agent':'Mozilla/5.0'}
url='https://www.nutrition-charts.com/?s=jimmy+johns'
resp=requests.get(url, headers=headers)
soup=BeautifulSoup(resp.text, 'html.parser')
for a in soup.select('a'):
    text=a.get_text(strip=True)
    if 'jimmy' in text.lower():
        print(text, a.get('href'))
