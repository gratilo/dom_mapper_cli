#!/usr/bin/env python3
"""
DOM Mapper Pro - Универсальный UI сканер для автотестов
Автоопределение SPA/статических сайтов + семантическая классификация
"""

import asyncio
import json
import argparse
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from playwright.async_api import async_playwright
from semantic_classifier import SemanticDOMClassifier

# ВАЖНО: эти две функции вынесены в utils.py
from utils import _base_css_css_strategy, _base_css_id_tag_strategy


class DOMMapper:
    def __init__(self, url: str, headless: bool = True):
        self.url = url
        self.headless = headless
        self.raw_elements: list[dict] = []
        self.classifier = SemanticDOMClassifier()

    async def scan(self):
        """Универсальное сканирование"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()

            page.on("console", lambda msg: print(f"📢 [{msg.type}]: {msg.text[:120]}"))
            page.on("pageerror", lambda err: print(f"❌ JS: {err}"))

            print(f"🌐 Сканирую: {self.url}")
            await self._universal_scan(page)

            await browser.close()

    async def _universal_scan(self, page):
        await page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)

        initial_count = await self._quick_check(page)
        print(f"📊 Начало: {initial_count} элементов")

        if initial_count > 8:
            print("✅ Похоже на статический сайт")
            self.raw_elements = await self._scan_page(page)
        else:
            print("🔄 Похоже на SPA/динамический сайт → адаптивное ожидание")
            self.raw_elements = await self._spa_adaptive_scan(page, initial_count)

    async def _quick_check(self, page) -> int:
        return len(
            await page.query_selector_all(
                "button, a[href], input:not([type=hidden]), [role=button], [role=link]"
            )
        )

    async def _spa_adaptive_scan(self, page, initial_count: int):
        strategies = [("fast", 2000), ("normal", 4000), ("heavy", 7000), ("max", 10_000)]

        last = []
        for name, timeout in strategies:
            print(f"  ⏳ {name} ({timeout/1000}s)")
            await page.wait_for_timeout(timeout)

            elements = await self._scan_page(page)
            last = elements

            if (len(elements) > max(8, initial_count * 2)) or (len({e["tag"] for e in elements}) > 4):
                print(f"    ✅ Стабильно: {len(elements)} элементов")
                return elements

            print(f"    🔄 Ещё ждём... ({len(elements)})")

        print("⚠️ Fallback: беру последнее состояние DOM")
        return last

    async def _scan_page(self, page):
        """Извлечение UI элементов - чистый Python с Playwright API"""
        
        combined_selector = ', '.join([
            'button', 'input:not([type=hidden])', 'select', 'textarea',
            'a[href]', '[role="button"]', '[role="link"]', '[onclick]',
            'nav', 'header', 'footer', 'form', 'aside',
            '.btn', '.button', '.card', '.sidebar', 'span'
            '[data-testid]', '[data-cy]', '[data-test]',
            '[tabindex]:not([tabindex="-1"])'
        ])
        
        all_locators = await page.locator(combined_selector).all()
        elements = []
        
        for idx, locator in enumerate(all_locators[:400]):
            try:
                is_visible = await locator.is_visible(timeout=100)
                if not is_visible:
                    continue
                
                el_data = await self._extract_element_data(locator, idx)
                if el_data:
                    elements.append(el_data)
                    
            except Exception as e:
                # Можно добавить для отладки: print(f"⚠️ Ошибка элемента {idx}: {e}")
                continue
        
        # Генерируем локаторы для всех собранных элементов
        from utils import generate_smart_xpath, _base_css_css_strategy
        
        for el in elements:
            try:
                el["xpath"] = generate_smart_xpath(el)
                el["css"] = _base_css_css_strategy(el)
            except Exception as e:
                # Fallback на случай ошибки
                el["xpath"] = f"//{el.get('tag', 'div')}"
                el["css"] = el.get('tag', 'div')
        
        print(f"✅ Найдено элементов: {len(elements)}")  # Для отладки
        return elements



    async def _extract_element_data(self, locator, index: int) -> dict | None:
        """Извлекает данные из одного элемента"""
        try:
            # Получаем тег
            tag = await locator.evaluate('el => el.tagName.toLowerCase()')
            
            # Получаем текст
            try:
                text = (await locator.inner_text(timeout=100)).strip()[:120]
            except:
                text = ""
            
            # Получаем атрибуты
            attributes = await locator.evaluate(
                'el => Object.fromEntries([...el.attributes].map(a => [a.name, a.value]))'
            )
            
            # Парсим классы
            classes = attributes.get('class', '').split() if attributes.get('class') else []
            
            return {
                'index': index,
                'tag': tag,
                'text': text,
                'classes': [c for c in classes if c],  # Убираем пустые
                'id_attr': attributes.get('id'),
                'name': attributes.get('name'),
                'role': attributes.get('role'),
                'type': attributes.get('type'),
                'placeholder': attributes.get('placeholder'),
                'href': attributes.get('href'),
                'attributes': attributes,
                'visible': True
            }
            
        except Exception as e:
            return None


    def scan_with_semantics(self):
        semantic_elements = []
        for el in self.raw_elements:
            semantic_el = self.classifier.classify_element(el)
            merged = {**el, **semantic_el.__dict__}  # сохраняем всё из raw

            merged["category"] = merged.get("category") or "uncategorized"
            merged["css"] = merged.get("css") or "div"
            merged["xpath"] = merged.get("xpath") or "//div"
            merged["text"] = merged.get("text") or ""

            semantic_elements.append(merged)

        return self._generate_semantic_report(semantic_elements)

    def _generate_semantic_report(self, semantic_elements: list[dict]) -> dict:
        report = {
            "url": self.url,
            "timestamp": datetime.now().isoformat(),
            "total_elements": len(semantic_elements),
            "categories": len({el.get("category", "uncategorized") for el in semantic_elements}),
            "by_category": {},
            "top_elements": semantic_elements[:50],
        }

        for el in semantic_elements:
            cat = el.get("category", "uncategorized")
            report["by_category"].setdefault(cat, []).append(el)

        return report


    @staticmethod
    def _norm_text(s: str) -> str:
        s = (s or "").strip()
        return re.sub(r"\s+", " ", s)

    def _quote_for_pw(self, text: str) -> str:
    # Playwright в доках обычно показывает двойные кавычки; json.dumps даст корректное экранирование
    # вернёт строку вида: "Найти событие"
        return json.dumps(text, ensure_ascii=False)

    def _css_plus_text_or_nth(self, base_css: str, el: dict, seen: defaultdict) -> str:
        text = self._norm_text(el.get("text", ""))
        tag = el.get("tag") or "div"


        if 1 <= len(text) <= 40:
            return f"{tag}:has-text({self._quote_for_pw(text)})"

        k = seen[base_css]
        seen[base_css] += 1
        return f"{base_css} >> nth={k}"


    def _xpath_plus_text_or_nth(self, xpath: str, el: dict, seen: defaultdict) -> str:
        text = self._norm_text(el.get("text", ""))


        if 1 <= len(text) <= 40:
            return f"xpath={xpath} >> text={json.dumps(text, ensure_ascii=False)}"


        key = f"{xpath}"
        k = seen[key]
        seen[key] += 1
        return f"{xpath} >> nth={k}"

    def generate_locator_classes(self, elements: list[dict], strategy: str) -> str:
        """
        Генерирует классы локаторов.
        CSS/ID_TAG: css=<base> >> text="..." или css=<base> >> nth=<n>  [web:20][web:16]
        XPath: просто xpath
        Text: просто text=
        """
        strategy = (strategy or "css").lower()
        by_category: dict[str, list[dict]] = {}

        # счетчик nth для каждого base_css
        seen = defaultdict(int)

        for el in elements:
            cat = el.get("category", "uncategorized")

            if strategy == "css":
                base = _base_css_css_strategy(el) or (el.get("css") or el.get("tag") or "div")
                locator = self._css_plus_text_or_nth(base, el, seen)

            elif strategy == "id_tag":
                base = _base_css_id_tag_strategy(el) or (el.get("css") or el.get("tag") or "div")
                locator = self._css_plus_text_or_nth(base, el, seen)

            elif strategy == "xpath":
                locator = el.get("xpath") or "//div"

            elif strategy == "text":
                text = self._norm_text(el.get("text", ""))
                locator = f"text={json.dumps(text, ensure_ascii=False)}" if text else "text=\"\""
            
            elif strategy == "xpath_text":
                xpath = el.get("xpath") or "//div"
                locator = self._xpath_plus_text_or_nth(xpath, el, seen)

            else:
                # fallback
                base = _base_css_css_strategy(el) or (el.get("css") or el.get("tag") or "div")
                locator = self._css_plus_text_or_nth(base, el, seen)

            el2 = dict(el)
            el2["locator"] = locator
            by_category.setdefault(cat, []).append(el2)

        out = []
        for category, group in by_category.items():
            class_name = f"{category.replace('-', '_').title()}Locators"
            lines = [f"class {class_name}:"]

            used_names = set()
            group_sorted = sorted(group, key=lambda x: x.get("confidence", 0), reverse=True)

            for el in group_sorted[:60]:
                name = self._make_locator_name(el)
                if name in used_names:
                    name = f"{name}_{el.get('index', 0)}"
                used_names.add(name)

                loc = (el.get("locator") or "css=div").replace("\\", "\\\\").replace("'", "\\'")
                comment = self._norm_text(el.get("text") or el.get("placeholder") or "")[:60]
                lines.append(f"    {name} = '{loc}'  # {comment}")

            out.append("\n".join(lines))

        return "\n\n".join(out)

    def _make_locator_name(self, el: dict) -> str:
        parts = []
        text = self._norm_text(el.get("text") or "")
        if text and len(text) < 20:
            parts.append(text.replace(" ", "_").replace("-", "_").lower())

        if el.get("id_attr"):
            parts.append(str(el["id_attr"]).replace("-", "_"))

        classes = el.get("classes") or []
        if not parts and classes:
            parts.append(str(classes[0]).replace("-", "_"))

        name = "_".join(parts)[:30] or f"element_{el.get('index', 0)}"
        return name.upper()

    def get_report(self) -> dict:
        return {
            "url": self.url,
            "timestamp": datetime.now().isoformat(),
            "total_elements": len(self.raw_elements),
            "visible_elements": len(self.raw_elements),
            "sample": self.raw_elements[:5],
        }


async def interactive_locator_generation(mapper: DOMMapper, report: dict):
    print("\n🎛️  ВЫБЕРИТЕ СТРАТЕГИЮ ЛОКАТОРОВ:")
    print("1. CSS (css=<base> >> text/nth)")
    print("2. XPath")
    print("3. Text")
    print("4. ID/Tag (css=<base> >> text/nth)")
    print("5. XPath + Text (xpath=<...> >> text/nth)")
    print("6. Все стратегии (4 файла)")


    choice = input("Выбор (1-6) [1]: ").strip() or "1"
    choice_to_strategy = {"1": "css", "2": "xpath", "3": "text", "4": "id_tag"}

    elements = []
    for group in report.get("by_category", {}).values():
        elements.extend(group)

    if choice == "5":
        for s in ("css", "xpath", "text", "id_tag"):
            Path(f"locators_{s}.py").write_text(mapper.generate_locator_classes(elements, s), encoding="utf-8")
            print(f"✅ locators_{s}.py")
    if choice == "6":
        for s in ("css", "xpath", "text", "id_tag", "xpath_text"):
            Path(f"locators_{s}.py").write_text(mapper.generate_locator_classes(elements, s), encoding="utf-8")
            print(f"✅ locators_{s}.py")
    else:
        s = choice_to_strategy.get(choice, "css")
        Path("locators.py").write_text(mapper.generate_locator_classes(elements, s), encoding="utf-8")
        print(f"✅ locators.py ({s})")


def print_summary(report: dict):
    by_cat = report.get("by_category") or {}
    if not by_cat:
        return
    print("\n📊 РЕЗУЛЬТАТ:")
    for cat, els in list(by_cat.items())[:8]:
        print(f"  {cat:14}: {len(els)} элементов")


async def main():
    parser = argparse.ArgumentParser(description="DOM Mapper Pro")
    parser.add_argument("url", nargs="?", help="URL сайта (если не указан — спросит)")
    parser.add_argument("--output", "-o", default="ui_map.json")
    parser.add_argument("--pytest", "-p", action="store_true", help="Интерактивная генерация locators.py")
    parser.add_argument("--headed", action="store_true", help="Открыть браузер (не headless)")
    parser.add_argument("--no-semantic", action="store_true")

    args = parser.parse_args()

    url = args.url or input("🌐 URL сайта: ").strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    mapper = DOMMapper(url, headless=not args.headed)
    await mapper.scan()

    report = mapper.get_report() if args.no_semantic else mapper.scan_with_semantics()

    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ JSON: {args.output} ({report['total_elements']} элементов)")

    if args.pytest and not args.no_semantic:
        await interactive_locator_generation(mapper, report)

    print_summary(report)


if __name__ == "__main__":
    asyncio.run(main())
