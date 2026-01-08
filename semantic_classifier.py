# semantic_classifier.py
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class SemanticElement:
    selector: str
    xpath: str
    css: str
    category: str
    subcategory: str
    confidence: float
    text: str
    role: str = ""

class SemanticDOMClassifier:
    def classify_element(self, element_data: Dict) -> SemanticElement:
        """Простая классификация (расширяемая)"""
        tag = element_data.get('tag', '').lower()
        classes = element_data.get('classes', [])
        text = element_data.get('text', '').lower()
        
        # Правила классификации
        if tag == 'button' or 'btn' in ' '.join(classes) or element_data.get('role') == 'button':
            return SemanticElement(
                selector=f"button.{classes[0] if classes else ''}",
                xpath=element_data.get('xpath', ''),
                css=element_data.get('css', f"button"),
                category="buttons",
                subcategory="primary" if 'primary' in ' '.join(classes) else "secondary",
                confidence=0.95,
                text=element_data.get('text', '')
            )
        
        if 'a' in tag and element_data.get('href'):
            return SemanticElement(
                selector="a[href]",
                xpath=element_data.get('xpath', ''),
                css="a[href]",
                category="navigation",
                subcategory="link",
                confidence=0.92,
                text=element_data.get('text', '')
            )
        
        if tag == 'input':
            return SemanticElement(
                selector="input",
                xpath=element_data.get('xpath', ''),
                css="input",
                category="forms",
                subcategory=element_data.get('type', 'text'),
                confidence=0.90,
                text=element_data.get('placeholder', '')
            )
        
        # Fallback
        return SemanticElement(
            selector=tag,
            xpath=element_data.get('xpath', ''),
            css=tag,
            category="containers",
            subcategory="generic",
            confidence=0.5,
            text=element_data.get('text', '')
        )
