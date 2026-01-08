# dom_mapper_cli.py
import asyncio
import json
import argparse
from playwright.async_api import async_playwright
from datetime import datetime

class DOMMapper:
    def __init__(self, url: str, headless: bool = False):
        self.url = url
        self.headless = headless
        self.elements = []
    
    async def extract_elements(self, page):
        """Извлекает элементы через JavaScript"""
        elements = await page.evaluate("""
            () => {
                const selectors = 'button, input, [onclick], a[href], form, select, textarea, [role="button"]';
                return Array.from(document.querySelectorAll(selectors)).map((el, idx) => {
                    const getXPath = (element) => {
                        if (element.id !== '')
                            return "//*[@id='" + element.id + "']";
                        if (element === document.body)
                            return element.tagName.toLowerCase();
                        const ix = Array.from(element.parentNode.childNodes).indexOf(element) + 1;
                        return getXPath(element.parentNode) + "/" + element.tagName.toLowerCase() + "[" + ix + "]";
                    };
                    
                    return {
                        index: idx,
                        tag: el.tagName.toLowerCase(),
                        text: el.innerText?.trim()?.substring(0, 100) || '',
                        id: el.id || null,
                        name: el.name || null,
                        classes: Array.from(el.classList),
                        xpath: getXPath(el),
                        visible: el.offsetParent !== null,
                        type: el.type || null,
                        placeholder: el.placeholder || null
                    };
                });
            }
        """)
        return elements
    
    async def scan(self):
        """Главный метод сканирования"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            
            print(f"[*] Сканирую {self.url}...")
            await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_selector("text=Бег, меняющий жизнь!", timeout=30000)
            self.elements = await self.extract_elements(page)
            print(f"[✓] Найдено {len(self.elements)} элементов")
            
            await browser.close()
            return self.get_report()
    
    def get_report(self):
        """Генерирует отчет"""
        return {
            'url': self.url,
            'timestamp': datetime.now().isoformat(),
            'total_elements': len(self.elements),
            'visible_elements': sum(1 for e in self.elements if e['visible']),
            'elements': self.elements
        }
    
    def export_json(self, filename: str):
        """Экспортирует в JSON"""
        report = self.get_report()
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[✓] Результаты сохранены в {filename}")
    
    def export_python_locators(self, filename: str):
        """Экспортирует локаторы в Python класс"""
        template = """# Auto-generated locators from DOM Mapper
class Locators:
{locators}
"""
        locators = []
        for el in self.elements:
            name = el.get('id') or el.get('name') or f"element_{el['index']}"
            name = name.replace('-', '_').replace(' ', '_').upper()
            xpath = el['xpath'].replace('"', '\\"')
            locators.append(f"    {name} = (By.XPATH, \"{xpath}\")")
        
        content = template.format(locators='\n'.join(locators))
        with open(filename, 'w') as f:
            f.write(content)
        print(f"[✓] Python локаторы сохранены в {filename}")

async def main():
    parser = argparse.ArgumentParser(description='DOM Mapper - автоматический сканер элементов')
    parser.add_argument('url', help='URL страницы для сканирования')
    parser.add_argument('--output', '-o', default='dom_map.json', help='Файл для сохранения')
    parser.add_argument('--python', '-p', help='Экспортировать в Python класс')
    parser.add_argument('--headless', action='store_true', default=True)
    
    args = parser.parse_args()
    
    mapper = DOMMapper(args.url, headless=args.headless)
    await mapper.scan()
    mapper.export_json(args.output)
    
    if args.python:
        mapper.export_python_locators(args.python)

if __name__ == '__main__':
    asyncio.run(main())
