"""契约自检:schemas.json 可解析且 example 全部通过自身 schema 校验。"""
import json
from pathlib import Path

import jsonschema

DOCS = Path(__file__).parent.parent / "docs"


def load_schemas():
    return json.loads((DOCS / "schemas.json").read_text(encoding="utf-8"))


def test_every_example_validates():
    for name, spec in load_schemas().items():
        schema = dict(spec["schema"])
        # 展开 $ref 到同文件兄弟 schema
        if "properties" in schema:
            for prop in schema["properties"].values():
                if "$ref" in prop:
                    ref_name = prop["$ref"].split("/")[2]
                    prop.pop("$ref")
                    prop.update(load_schemas()[ref_name]["schema"])
        jsonschema.validate(spec["example"], schema)


def test_contracts_md_covers_all_schemas():
    text = (DOCS / "CONTRACTS.md").read_text(encoding="utf-8")
    for name in load_schemas():
        assert name in text, f"CONTRACTS.md 未提及 {name}"
