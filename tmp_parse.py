import re
import requests

headers={'User-Agent':'Mozilla/5.0'}
text=requests.get('https://fastfoodnutrition.org/jimmy-johns', headers=headers).text
matches=re.findall(r'{"name":".*?"}', text)
print(len(matches))
