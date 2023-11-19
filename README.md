# Get Started

```python
python3 -m venv .venv
```


for OSX

```
source ./.venv/bin/active
```


for Window

```
./.venv/Scripts/activate
```

```
pip3 install -r requirements.txt
```

```
python3 main.py
```

# Troubleshootings

### ImportError: cannot import name 'Mapping' from 'collections'

Go to `.venv/lib/python3.11/site-packages/prompt_toolkit/styles/from_dict.py` and fix line 9 to

```
from collections.abc import Mapping
```
