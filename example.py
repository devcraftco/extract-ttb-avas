import os
import random
import requests
import sys

from lib.parser import Parser

established_avas_url = sys.argv[1] if len(sys.argv) >= 2 else 'https://www.ttb.gov/wine/established-avas'
if established_avas_url.lower().startswith('http://') or established_avas_url.lower().startswith('https://'):
    print(f'Using URL: {established_avas_url}')
    html = requests.get(established_avas_url).text
else:
    print(f'Using file: {established_avas_url}')
    if not os.path.exists(established_avas_url):
        print(f'{established_avas_url}: file not found')
        exit(1)
    with open(established_avas_url, 'r') as file:
        html = file.read()

total_established_avas, multi_state_avas, avas = Parser().parse(html)

print(f'{total_established_avas} established AVAs reported')
total_parsed_avas = len(multi_state_avas) + len(avas)
print(f'{total_parsed_avas} parsed AVAs ({len(multi_state_avas)} multi-state AVAs, {len(avas)} AVAs)')
print('** Random Multi-State AVA **')
print(multi_state_avas[random.randrange(len(multi_state_avas))])
print('** Random AVA **')
print(avas[random.randrange(len(avas))])
