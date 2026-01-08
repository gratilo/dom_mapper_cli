import re
import json
from collections import defaultdict

def _norm_text(self, s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _base_css_css_strategy(el: dict) -> str:
    """База для стратегии CSS: id > data-* > aria-label > tag.class > tag"""
    tag = el.get("tag") or "div"
    attrs = el.get("attributes") or {}
    classes = el.get("classes") or []

    if el.get("id_attr"):
        return f"#{el['id_attr']}"

    for a in ("data-testid", "data-cy", "data-test"):
        if attrs.get(a):
            return f'[{a}="{attrs[a]}"]'

    if attrs.get("aria-label"):
        return f'[aria-label="{attrs["aria-label"]}"]'

    if classes:
        return f"{tag}.{classes[0]}"

    return tag

def _base_css_id_tag_strategy(el: dict) -> str:
    """База для стратегии ID_TAG: id/data-* > name > role > tag.class > tag"""
    tag = el.get("tag") or "div"
    attrs = el.get("attributes") or {}
    classes = el.get("classes") or []

    if el.get("id_attr"):
        return f"#{el['id_attr']}"

    for a in ("data-testid", "data-cy", "data-test", "name"):
        if attrs.get(a):
            return f'[{a}="{attrs[a]}"]'

    if el.get("role"):
        return f'[role="{el["role"]}"]'

    if classes:
        return f"{tag}.{classes[0]}"

    return tag
