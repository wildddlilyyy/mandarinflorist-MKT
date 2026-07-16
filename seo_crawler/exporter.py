from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


CSV_COLUMNS = [
    "url",
    "status_code",
    "title",
    "title_length",
    "meta_description",
    "meta_description_length",
    "h1_count",
    "h1_text",
    "canonical",
    "image_count",
    "images_missing_alt",
    "images_missing_alt_ratio",
    "internal_links_count",
    "external_links_count",
    "error",
]


def export_csv(rows: list[dict[str, Any]], output_path: str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    dataframe = pd.DataFrame(rows, columns=CSV_COLUMNS)
    dataframe.to_csv(path, index=False, encoding="utf-8-sig")
    return path

