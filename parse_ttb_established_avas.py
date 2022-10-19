import json
import os
import re
import requests
import sys
from typing import Callable, Any

from py_parse import Parser, Node


def normalize_text_value(value: str) -> str:
    return re.sub(r',$', '', re.sub(r' {2,}', ' ', re.sub(r'[^-A-Za-z,. ]', '', re.sub(r'\([^)]*\)', '', value.replace('–', '-').replace('—', '-').replace('--', '-'))))).strip()

def extract_table_cell_list_values(node: Node) -> list:
    if len(node.children(lambda e: e.tag == 'p')) > 0:
        p = node.child(lambda e: e.tag == 'p')
        if 'excluded from' in p.text:
            return []
        if len(p.descendants(lambda e: e.tag == 'strong' and e.class_ == 'colorRed')) > 0:
            return []
        text = normalize_text_value(p.text)
        return [text] if len(text) > 0 else []
    elif len(node.children(lambda e: e.tag == 'ul')) > 0:
        return list(map(lambda li: normalize_text_value(li.text), node.descendants(lambda e: e.tag == 'li' and len(e.descendants(lambda e: e.tag == 'strong' and e.class_ == 'colorRed')) < 1)))
    text = node.text.strip()
    if len(text) < 1:
        return []

    return list(map(lambda v: v.strip(), re.split(r'\s*,\s*', node.text)))

def find_parent(node: Node, filter_: Callable[[Any], bool] = None) -> Node:
    if not node.has_parent():
        return None

    parent = node.parent
    if filter_ is None:
        return parent
    elif filter_(parent):
        return parent
    else:
        return find_parent(parent, filter_)


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

parsed = Parser().parse(html)

p = parsed.find(lambda e: e.tag == 'p' and e.text.startswith('Currently, there are'))
total_established_avas = int(p.descendant(lambda e: e.tag == 'strong').text)
print(f'Total established AVAs: {total_established_avas}')

# parse multi-state AVAs
multi_state_avas = {}
multi_state_anchor = parsed.find(lambda e: e.tag == 'a' and 'id' in e and e.id == 'Table-2')
multi_state_table = multi_state_anchor.parent.next_sibling(
    lambda e: e.tag == 'table' and len(e.descendants(lambda e: e.tag == 'strong' and e.text.strip().startswith('Table 2: Multi-State AVAs'))) > 0
)
tr = multi_state_table.descendant(lambda e: e.tag == 'tr')
while tr.has_next_node():
    tr = tr.next_sibling()
    if len(tr.children()) < 5:
        continue
    tds = tr.children()
    name = normalize_text_value(tds[0].descendant(lambda e: e.tag == 'strong').text)
    if name == 'AVA Name':
        # ignore heading of the table
        continue

    states = list(map(lambda li: li.text.strip(), tds[1].descendants(lambda e: e.tag == 'li')))
    within = extract_table_cell_list_values(tds[2])
    contains = extract_table_cell_list_values(tds[3])
    cfr_a = tds[4].descendant(lambda e: e.tag == 'a')
    cfr_section = cfr_a.text.strip()
    cfr_link = cfr_a.href.strip()
    multi_state_avas[name] = dict(
        name=name,
        states=states,
        within=within,
        contains=contains,
        cfr_section=cfr_section,
        cfr_link=cfr_link,
    )

# parse single-state AVAs
avas = {}
name_map = {
    'Eola -Amity Hills': 'Eola-Amity Hills',
}
contains_map = {
    'The Hamptons': 'The Hamptons, Long Island',
    'Arroyo Grande': 'Arroyo Grande Valley',
    'Green Valley of the Russian River Valley': 'Green Valley of Russian River Valley',
    'Dry Creek': 'Dry Creek Valley',
    'San Pasquale Valley': 'San Pasqual Valley',
}
state_anchors_table = parsed.find(lambda e: e.tag == 'table' and len(e.descendants(lambda e: e.tag == 'tr' and e.class_ == 'anchors')) > 0)
state_anchors_trs = state_anchors_table.descendants(lambda e: e.tag == 'tr' and e.class_ == 'anchors')
for state_anchor_tr in state_anchors_trs:
    state_anchors = state_anchor_tr.descendants(lambda e: e.tag == 'a')
    for state_anchor in state_anchors:
        state = state_anchor.text.strip()
        state_anchor_id = state_anchor.href[1:]
        tr = find_parent(
            parsed.find(lambda e: e.tag == 'a' and 'id' in e and e.id == state_anchor_id),
            lambda e: e.tag == 'tr'
        )
        # iterate through next siblings until we find the <tr> containing a <td colspan="5">, which signals the section end
        while tr.has_next_node():
            tr = tr.next_sibling()
            if len(tr.descendants(lambda e: e.tag == 'td' and 'colspan' in e and e.colspan == '5')) > 0:
                break
            tds = tr.children()
            name = ' '.join(map(lambda strong: strong.text.strip(), tds[0].descendants(lambda e: e.tag == 'strong')))
            name = normalize_text_value(name)
            name = name_map[name] if name in name_map else name
            counties = extract_table_cell_list_values(tds[1])
            within = extract_table_cell_list_values(tds[2])
            contains = list(map(lambda c: c if c not in contains_map else contains_map[c], extract_table_cell_list_values(tds[3])))
            cfr_a = tds[4].descendant(lambda e: e.tag == 'a')
            cfr_section = cfr_a.text.strip()
            cfr_link = cfr_a.href.strip()
            avas[name] = dict(
                state=state,
                name=name,
                counties=counties,
                within=within,
                contains=contains,
                cfr_section=cfr_section,
                cfr_link=cfr_link,
            )

# validate within and contains
valid = True
for ava in avas.values():
    for ava_name in ava['within']:
        if ava_name not in avas and ava_name not in multi_state_avas:
            print(f'ava [{ava["name"]}] within [{ava_name}] not found')
            valid = False
    for ava_name in ava['contains']:
        if ava_name not in avas and ava_name not in multi_state_avas:
            print(f'ava [{ava["name"]}] contains [{ava_name}] not found')
            valid = False
if not valid:
    # data is not internally consistent
    exit(1)

total_avas = len(avas) + len(multi_state_avas)
print(f'Total parsed AVAs: {total_avas} ({len(avas)} AVAs, {len(multi_state_avas)} multi-state AVAs)')
if total_avas != total_established_avas:
    print('Counts do not match!')
    exit(1)

print('Writing multi_state_avas.json...')
with open('multi_state_avas.json', 'w') as file:
    json.dump(list(multi_state_avas.values()), file)

print('Writing avas.json...')
with open('avas.json', 'w') as file:
    json.dump(list(avas.values()), file)
