## About

This library will attempt to normalize and parse the established AVAs published on the
TTB website, returning structured information that can be used programmatically. The TTB website has many inconsistencies not only in the AVA names but also the DOM structure used to publish the established AVAs. As the page is updated, this library may also need to be updated.

If you discover any parsing, normalization, or correction problems, please open an issue on this project.

## Requirements

* Python 3.x
* pip

## Installation

1. Clone this repo
2. `pip install -r requirements.txt`

## Usage

Please see `example.py` for a working example that uses this library.

```python
import requests
from lib.parser import Parser

html = requests.get('https://www.ttb.gov/wine/established-avas').text
total_established_avas, multi_state_avas, avas = Parser().parse(html)

print(f'{total_established_avas} established AVAs reported')
total_parsed_avas = len(multi_state_avas) + len(avas)
print(f'{total_parsed_avas} parsed AVAs ({len(multi_state_avas)} multi-state AVAs, {len(avas)} AVAs)')
```
