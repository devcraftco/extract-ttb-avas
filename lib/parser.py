import re
from typing import Any, Callable, Dict, List, Tuple

from py_parse import Parser as PyParser, Node


class Parser(object):

    def _normalize_text_value(self, value: str) -> str:
        """
        this normalization is necessary because the TTB established AVAs have various inconsistencies in how they're listed
        """
        return re.sub(
            r',$',  # remove trailing ,
            '',
            re.sub(
                r' {2,}',   # squash 2+ spaces to a single space
                ' ',
                re.sub(
                    r'[^-A-Za-z,. ]',   # remove non-alpha, comma, -, ., and space chars
                    '',
                    re.sub(
                        r'\([^)]*\)',   # remove parens and any values between them
                        '',
                        value \
                            .replace('–', '-') \
                            .replace('—', '-') \
                            .replace('--', '-')
                    )
                )
            )
        ).strip()

    def _extract_table_cell_list_values(self, node: Node) -> Tuple[List, List]:
        """
        Single and multiple value lists are structured differently in the DOM
        """
        if len(node.children(lambda e: e.tag == 'p')) > 0:
            p = node.child(lambda e: e.tag == 'p')
            if 'excluded from' in p.text:
                return ([], [])
            text = self._normalize_text_value(p.text)
            if len(p.descendants(lambda e: e.tag == 'strong' and e.class_ == 'colorRed' and e.text.strip() == '*')) > 0:
                return ([], [text] if len(text) > 0 else [])
            return ([text] if len(text) > 0 else [], [])
        elif len(node.children(lambda e: e.tag == 'ul')) > 0:
            ul = node.child(lambda e: e.tag == 'ul')
            lis = ul.children(lambda e: e.tag == 'li')
            in_values = []
            overlap_values = []
            for li in lis:
                text = self._normalize_text_value(li.text)
                if len(text) > 0:
                    if len(li.descendants(lambda e: e.tag == 'strong' and e.class_ == 'colorRed' and e.text.strip() == '*')) > 0:
                        overlap_values.append(text)
                    else:
                        in_values.append(text)
            return (in_values, overlap_values)
        text = node.text.strip()
        if len(text) < 1:
            return ([], [])

        return (list(map(lambda v: v.strip(), re.split(r'\s*,\s*', node.text))), [])

    def _find_parent(self, node: Node, filter_: Callable[[Any], bool] = None) -> Node:
        if not node.has_parent():
            return None

        parent = node.parent
        if filter_ is None:
            return parent
        elif filter_(parent):
            return parent
        else:
            return self._find_parent(parent, filter_)

    def _extract_total_established_avas(self) -> int:
        p = self.parsed.find(lambda e: e.tag == 'p' and e.text.startswith('Currently, there are'))
        return int(p.descendant(lambda e: e.tag == 'strong').text)

    def _parse_multi_state_avas(self) -> Dict:
        multi_state_avas = {}
        multi_state_anchor = self.parsed.find(lambda e: e.tag == 'a' and 'id' in e and e.id == 'Table-2')
        multi_state_table = multi_state_anchor.parent.next_sibling(
            lambda e: e.tag == 'table' and len(e.descendants(lambda e: e.tag == 'strong' and e.text.strip().startswith('Table 2: Multi-State AVAs'))) > 0
        )
        tr = multi_state_table.descendant(lambda e: e.tag == 'tr')
        while tr.has_next_node():
            tr = tr.next_sibling()
            if len(tr.children()) < 5:
                continue
            tds = tr.children()
            name = self._normalize_text_value(tds[0].descendant(lambda e: e.tag == 'strong').text)
            if name == 'AVA Name':
                # ignore heading of the table
                continue

            states = list(map(lambda li: li.text.strip(), tds[1].descendants(lambda e: e.tag == 'li')))
            within, _ = self._extract_table_cell_list_values(tds[2])
            contains, _ = self._extract_table_cell_list_values(tds[3])
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
        return multi_state_avas

    def _parse_avas(self) -> Dict:
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
        state_anchors_table = self.parsed.find(lambda e: e.tag == 'table' and len(e.descendants(lambda e: e.tag == 'tr' and e.class_ == 'anchors')) > 0)
        state_anchors_trs = state_anchors_table.descendants(lambda e: e.tag == 'tr' and e.class_ == 'anchors')
        for state_anchor_tr in state_anchors_trs:
            state_anchors = state_anchor_tr.descendants(lambda e: e.tag == 'a')
            for state_anchor in state_anchors:
                state = state_anchor.text.strip()
                state_anchor_id = state_anchor.href[1:]
                tr = self._find_parent(
                    self.parsed.find(lambda e: e.tag == 'a' and 'id' in e and e.id == state_anchor_id),
                    lambda e: e.tag == 'tr'
                )
                # iterate through next siblings until we find the <tr> containing a <td colspan="5">, which signals the section end
                while tr.has_next_node():
                    tr = tr.next_sibling()
                    if len(tr.descendants(lambda e: e.tag == 'td' and 'colspan' in e and e.colspan == '5')) > 0:
                        break
                    tds = tr.children()
                    name = ' '.join(map(lambda strong: strong.text.strip(), tds[0].descendants(lambda e: e.tag == 'strong')))
                    name = self._normalize_text_value(name)
                    name = name_map[name] if name in name_map else name
                    counties, _ = self._extract_table_cell_list_values(tds[1])
                    within, within_overlaps = self._extract_table_cell_list_values(tds[2])
                    contains, contains_overlaps = self._extract_table_cell_list_values(tds[3])
                    contains = list(map(lambda c: c if c not in contains_map else contains_map[c], contains))
                    contains_overlaps = list(map(lambda c: c if c not in contains_map else contains_map[c], contains_overlaps))
                    overlaps = list(set(within_overlaps + contains_overlaps))
                    cfr_a = tds[4].descendant(lambda e: e.tag == 'a')
                    cfr_section = cfr_a.text.strip()
                    cfr_link = cfr_a.href.strip()
                    avas[name] = dict(
                        state=state,
                        name=name,
                        counties=counties,
                        within=within,
                        contains=contains,
                        overlaps=overlaps,
                        cfr_section=cfr_section,
                        cfr_link=cfr_link,
                    )
        return avas

    def validate(self, total_established_avas: int, multi_state_avas: Dict, avas: Dict) -> None:
        valid = True
        for ava in avas.values():
            for ava_name in ava['within']:
                if ava_name not in avas and ava_name not in multi_state_avas:
                    print(f'AVA [{ava["name"]}] has missing within AVA [{ava_name}]')
                    valid = False
            for ava_name in ava['contains']:
                if ava_name not in avas and ava_name not in multi_state_avas:
                    print(f'AVA [{ava["name"]}] has missing contains AVA [{ava_name}]')
                    valid = False
            for ava_name in ava['overlaps']:
                if ava_name not in avas and ava_name not in multi_state_avas:
                    print(f'AVA [{ava["name"]}] has missing overlaps AVA [{ava_name}]')
                    valid = False

        total_parsed_avas = len(avas) + len(multi_state_avas)
        if total_parsed_avas != total_established_avas:
            print(f'{total_established_avas} established AVAs reported, but only {total_parsed_avas} AVAs parsed')
            valid = False
        if not valid:
            raise RuntimeError('Inconsistencies detected in parsed data')

    def parse(self, content: str, return_dict: bool = False) -> Tuple[int, Any, Any]:
        self.parsed = PyParser().parse(content)
        total_established_avas = self._extract_total_established_avas()
        multi_state_avas = self._parse_multi_state_avas()
        avas = self._parse_avas()
        self.validate(total_established_avas, multi_state_avas, avas)
        return (
            total_established_avas,
            multi_state_avas if return_dict else list(multi_state_avas.values()),
            avas if return_dict else list(avas.values()),
        )
