import csv
import os
import re
import requests
import sys
import us

from lib.parser import Parser


def slug(name: str) -> str:
    return re.sub(r'[^-a-z]', '', name.lower().replace(' ', '-'))

def find_most_specific_within_ava(ava: dict, multi_state_avas: dict, avas: dict):
    if len(ava['within']) < 1:
        return None
    elif len(ava['within']) == 1:
        ava_name = ava['within'][0]
        return multi_state_avas[ava_name] if ava_name in multi_state_avas else avas[ava_name]
    avas = sorted(map(lambda ava_name: multi_state_avas[ava_name] if ava_name in multi_state_avas else avas[ava_name], ava['within']), key=lambda ava: len(ava['contains']))
    return avas[0]


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

total_established_avas, multi_state_avas, avas = Parser().parse(html, return_dict=True)


def write_ava(ava: dict, multi_state_avas: dict, avas: dict, ava_ids: dict, next_id: int, writer) -> int:
    state = us.states.lookup(ava['state'])
    if state is None:
        raise(f'Invalid state [{ava["state"]}]')

    parent_ava = find_most_specific_within_ava(ava, multi_state_avas, avas)
    if parent_ava is None:
        # use state-level AVA
        if state.name not in ava_ids:
            writer.writerow([
                next_id,
                state.name,
                'state',
                1,
                slug(state.name),
            ])
            ava_ids[state.name] = next_id
            next_id += 1
        parent_region_id = ava_ids[state.name]
    else:
        if parent_ava['name'] in multi_state_avas:
            # multi-state avas are written in the first pass
            parent_ava_name = f'{parent_ava["name"]} ({state.abbr})'
            parent_region_id = ava_ids[parent_ava_name]
        else:
            if parent_ava['name'] not in ava_ids:
                # parent ava hasn't been written yet; we need to write it first so we have a parent_id to use
                next_id = write_ava(parent_ava, multi_state_avas, avas, ava_ids, next_id, writer)
            parent_region_id = ava_ids[parent_ava['name']]
    writer.writerow([
        next_id,
        ava['name'],
        'region',
        parent_region_id,
        slug(ava['name']),
    ])
    ava_ids[ava['name']] = next_id
    return next_id + 1


print('Writing regions.csv...')
ava_ids = {'United States': 1}
id = 2
with open('regions.csv', 'w') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['id', 'name', 'type', 'parent_region_id', 'slug'])
    writer.writerow([1, 'United States', 'country', None, slug('United States')])
    for ava in multi_state_avas.values():
        for state_name in ava['states']:
            state = us.states.lookup(state_name)
            if state is None:
                raise(f'Invalid state [{state_name}]')
            if state.name not in ava_ids:
                ava_ids[state.name] = id
                writer.writerow([
                    id,
                    state.name,
                    'state',
                    1,
                    slug(state.name),
                ])
                id += 1
            ava_name = f'{ava["name"]} ({state.abbr})'
            ava_ids[ava_name] = id
            parent_ava = find_most_specific_within_ava(ava, multi_state_avas, avas)
            parent_ava_name = f'{parent_ava["name"]} ({state.abbr})' if parent_ava is not None else state.name
            writer.writerow([
                id,
                ava_name,
                'region',
                ava_ids[parent_ava_name],
                slug(ava_name)
            ])
            id += 1

    for ava in avas.values():
        if ava['name'] not in ava_ids:
            id = write_ava(ava, multi_state_avas, avas, ava_ids, id, writer)
