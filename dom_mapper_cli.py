# dom_mapper_cli.py
#!/usr/bin/env python3
"""
DOM Mapper Pro - Универсальный UI сканер для автотестов
Автоопределение SPA/статических сайтов + семантическая классификация
"""

import asyncio
import json
import argparse
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError
try:
    from semantic_classifier import SemanticDOMClassifier
except ImportError:
    print("❌ Создайте semantic_classifier.py!")
    exit(1)

class DOMMapper:
    def __init__(self, url: str, headless: bool = True):
        self.url = url
        self.headless = headless
        self.raw_elements = []
        self.classifier = SemanticDOMClassifier()

    async def scan(self):
        """🎯 Универсальное сканирование (главный метод)"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            
            # Диагностика
            page.on("console", lambda msg: print(f"📢 [{msg.type}]: {msg.text[:80]}"))
            page.on("pageerror", lambda err: print(f"❌ JS: {err}"))
            
            print(f"🌐 Сканирую: {self.url}")
            await self._universal_scan(page)
            
            await browser.close()
        return self.get_report()

    async def _universal_scan(self, page):
        """ Универсальный алгоритм для всех сайтов"""
        # Шаг 1: Базовая загрузка
        await page.goto(self.url, wait_until='domcontentloaded', timeout=60_000)
        
        # Шаг 2: Быстрая проверка
        initial_count = await self._quick_check(page)
        print(f"📊 Начало: {initial_count} элементов")
        
        if initial_count > 8:
            print("✅ Статический сайт")
            self.raw_elements = await self._scan_page(page)
        else:
            print("🔄 SPA/динамический → умное ожидание")
            self.raw_elements = await self._spa_adaptive_scan(page, initial_count)

    async def _quick_check(self, page) -> int:
        """Мгновенная проверка UI элементов"""
        return len(await page.query_selector_all(
            "button, a[href], input:not([type=hidden]), [role=button]"
        ))

    async def _spa_adaptive_scan(self, page, initial_count: int):
        """🎯 Адаптивное сканирование для SPA"""
        strategies = [
            ("fast", 2000),
            ("normal", 4000), 
            ("heavy", 7000),
            ("max", 10000)
        ]
        
        for name, timeout in strategies:
            print(f"  ⏳ {name} ({timeout/1000}s)")
            await page.wait_for_timeout(timeout)
            
            elements = await self._scan_page(page)
            
            # Критерии успеха
            if (len(elements) > max(8, initial_count * 2) or
                len(set(el['tag'] for el in elements)) > 4):
                print(f"    ✅ Стабильно: {len(elements)} элементов")
                return elements
            
            print(f"    🔄 Ещё ждём... ({len(elements)})")
        
        print("⚠️ Fallback")
        return await self._scan_page(page)

    async def _scan_page(self, page):
        """Извлечение всех UI элементов"""
        return await page.evaluate("""
            () => {
                const getXPath = (element) => {
                    if (element.id !== '') return `//*[@id='${element.id}']`;
                    if (element === document.body) return element.tagName.toLowerCase();
                    const ix = Array.from(element.parentNode.childNodes).indexOf(element) + 1;
                    return getXPath(element.parentNode) + `/${element.tagName.toLowerCase()}[${ix}]`;
                };
                
                const ui_selectors = [
                    'button', 'input:not([type=hidden])', 'select', 'textarea',
                    'a[href]', '[role="button"]', '[onclick]',
                    'nav', 'header', 'footer', 'form', 'aside',
                    '.btn', '.button', '.card', '.sidebar',
                    '[data-testid]', '[tabindex]:not([tabindex="-1"])'
                ].join(',');
                
                return Array.from(document.querySelectorAll(ui_selectors))
                    .map((el, idx) => ({
                        index: idx,
                        tag: el.tagName.toLowerCase(),
                        text: el.innerText?.trim()?.substring(0, 100) || '',
                        classes: Array.from(el.classList),
                        class_str: Array.from(el.classList).join(' '),
                        id_attr: el.id || null,
                        name: el.name || null,
                        role: el.getAttribute('role') || null,
                        type: el.type || null,
                        placeholder: el.placeholder || null,
                        href: el.href || null,
                        xpath: getXPath(el),
                        css: el.matches('[id]') ? `#${el.id}` : 
                             el.matches('[class]') ? `${el.tagName.toLowerCase()}.${Array.from(el.classList)[0]}` :
                             el.tagName.toLowerCase(),
                        rect: el.getBoundingClientRect(),
                        visible: el.offsetParent !== null && el.getBoundingClientRect().width > 0,
                        attributes: Object.fromEntries([...el.attributes].map(a => [a.name, a.value]))
                    }))
                    .filter(el => el.visible)
                    .slice(0, 200);  // Лимит для производительности
            }
        """)

    def scan_with_semantics(self):
        """Классификация элементов"""
        semantic_elements = []
        for el in self.raw_elements:
            semantic_el = self.classifier.classify_element(el)
            # Синхронизируем поля
            semantic_el.css = el.get('css', semantic_el.css)
            semantic_el.xpath = el.get('xpath', semantic_el.xpath)
            semantic_elements.append(semantic_el.__dict__)
        return self._generate_semantic_report(semantic_elements)

    def _generate_semantic_report(self, semantic_elements):
        report = {
            'url': self.url,
            'timestamp': datetime.now().isoformat(),
            'total_elements': len(semantic_elements),
            'categories': len(set(el['category'] for el in semantic_elements)),
            'by_category': {},
            'test_classes': self._generate_pytest_classes(semantic_elements),
            'top_elements': semantic_elements[:20]
        }
        
        # Группировка
        for el in semantic_elements:
            cat = el['category']
            report["by_category"].setdefault(cat, []).append(el)
        
        return report

    def _generate_pytest_classes(self, elements: list) -> str:
        """Генерация pytest локаторов"""
        by_category = {}
        for el in elements:
            by_category.setdefault(el['category'], []).append(el)
        
        classes = []
        for category, group in by_category.items():
            safe_name = category.replace('-', '_').title()
            locators = []
            
            for el in group[:10]:
                name = self._make_locator_name(el)
                css = el.get('css', el.get('selector', 'div')).replace("'", "\\'")
                locators.append(f"    {name} = '{css}'")
            
            classes.append(f"class {safe_name}Locators:\n" + 
                          "\n".join(locators))
        
        return "\n\n".join(classes)

    def _make_locator_name(self, el: dict) -> str:
        parts = []
        text = el.get('text', '').strip()
        if text and len(text) < 15:
            parts.append(text.replace(' ', '_').lower())
        if el.get('id_attr'):
            parts.append(el['id_attr'].replace('-', '_'))
        elif el.get('classes'):
            parts.append(el['classes'][0].replace('-', '_'))
        name = '_'.join(parts)[:25] or f"element_{el.get('index', 0)}"
        return name.replace(' ', '_').upper()

    def get_report(self):
        return {
            'url': self.url,
            'timestamp': datetime.now().isoformat(),
            'total_elements': len(self.raw_elements),
            'visible_elements': len(self.raw_elements),
            'sample': self.raw_elements[:5]
        }

async def main():
    parser = argparse.ArgumentParser(description='DOM Mapper Pro v2.0')
    parser.add_argument('url', help='URL сайта')
    parser.add_argument('--output', '-o', default='ui_map.json', help='JSON отчёт')
    parser.add_argument('--pytest', '-p', help='Pytest локаторы')
    parser.add_argument('--headless', '-H', action='store_true', default=True)
    parser.add_argument('--no-semantic', action='store_true', help='Без классификации')
    
    args = parser.parse_args()
    
    mapper = DOMMapper(args.url, headless=args.headless)
    await mapper.scan()
    
    if args.no_semantic:
        report = mapper.get_report()
    else:
        report = mapper.scan_with_semantics()
    
    # Сохраняем JSON
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), 'utf-8')
    print(f"✅ JSON: {args.output} ({report['total_elements']} элементов)")
    
    # Pytest классы
    if args.pytest:
        Path(args.pytest).write_text(report['test_classes'])
        print(f"✅ Pytest: {args.pytest}")
    
    # Статистика
    if 'by_category' in report:
        print("📊 Категории:")
        for cat, count in {k: len(v) for k, v in report['by_category'].items()}.items():
            print(f"  {cat}: {count}")

if __name__ == '__main__':
    asyncio.run(main())
