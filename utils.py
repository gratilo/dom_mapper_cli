# utils.py
import re
import json
from collections import defaultdict


def _escape_xpath_string(s: str) -> str:
    """Экранирует строку для XPath"""
    if "'" not in s:
        return f"'{s}'"
    if '"' not in s:
        return f'"{s}"'
    parts = s.split("'")
    return "concat('" + "',\"'\",'" .join(parts) + "')"


def _norm_text(s: str) -> str:
    """Нормализует текст"""
    s = (s or "").strip()
    return re.sub(r"\s+", " ", s)


def generate_smart_xpath(el: dict) -> str:
    """Генерирует умный XPath - ЧИСТЫЙ PYTHON"""
    attrs = el.get("attributes") or {}
    tag = el.get("tag") or "div"
    
    # 1. ID
    if el.get("id_attr"):
        return f"//*[@id='{el['id_attr']}']"
    
    # 2. data-* атрибуты
    for attr in ['data-testid', 'data-cy', 'data-test', 'data-qa']:
        val = attrs.get(attr)
        if val:
            return f"//*[@{attr}='{val}']"
    
    # 3. Текст
    text = _norm_text(el.get("text", ""))
    if 1 <= len(text) <= 50 and '\n' not in text:
        escaped = _escape_xpath_string(text)
        return f"//{tag}[contains(normalize-space(.), {escaped})]"
    
    # 4. name
    if el.get("name"):
        return f"//{tag}[@name='{el['name']}']"
    
    # 5. placeholder
    placeholder = el.get("placeholder") or attrs.get("placeholder")
    if placeholder and len(placeholder) <= 50:
        escaped = _escape_xpath_string(placeholder)
        return f"//{tag}[@placeholder={escaped}]"
    
    # 6. aria-label
    aria_label = attrs.get("aria-label")
    if aria_label:
        escaped = _escape_xpath_string(aria_label)
        return f"//{tag}[@aria-label={escaped}]"
    
    # 7. Классы
    classes = el.get("classes") or []
    meaningful = [c for c in classes if len(c) > 2 and not re.match(r'^[a-z]{1,2}\d+', c, re.I)]
    if meaningful:
        return f"//{tag}[contains(@class,'{meaningful[0]}')]"
    
    # 8. type
    el_type = el.get("type") or attrs.get("type")
    if el_type and tag in ("input", "button"):
        return f"//{tag}[@type='{el_type}']"
    
    # 9. role
    role = el.get("role") or attrs.get("role")
    if role:
        return f"//*[@role='{role}']"
    
    # 10. Fallback
    return f"//{tag}"


def _base_css_css_strategy(el: dict) -> str:
    """CSS селектор"""
    tag = el.get("tag") or "div"
    attrs = el.get("attributes") or {}
    classes = el.get("classes") or []

    if el.get("id_attr"):
        return f"#{el['id_attr']}"

    for a in ("data-test-id", "data-cy", "data-test"):
        if attrs.get(a):
            return f'[{a}="{attrs[a]}"]'

    if attrs.get("aria-label"):
        return f'[aria-label="{attrs["aria-label"]}"]'

    if classes:
        return f"{tag}.{classes[0]}"

    return tag


def _base_css_id_tag_strategy(el: dict) -> str:
    """ID/Tag стратегия"""
    tag = el.get("tag") or "div"
    attrs = el.get("attributes") or {}
    classes = el.get("classes") or []

    if el.get("id_attr"):
        return f"#{el['id_attr']}"

    for a in ("data-test-id", "data-cy", "data-test", "name"):
        if attrs.get(a):
            return f'[{a}="{attrs[a]}"]'

    if el.get("role"):
        return f'[role="{el["role"]}"]'

    if classes:
        return f"{tag}.{classes[0]}"

    return tag
