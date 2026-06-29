from __future__ import annotations

import json
from typing import Any

from sv_cli.utils import mask_mapping


def render(data: Any) -> str:
    return json.dumps(mask_mapping(data), indent=2, ensure_ascii=False)
