"""
HTML парсеры для различных сайтов

Этот пакет содержит специализированные парсеры для HTML сайтов:
- base_html.py - базовый HTML парсер
- bcs_parser.py - парсер для bcs-express.ru
"""

from .base_html import BaseHTMLParser
from .bcs_parser import BCSParser

__all__ = ['BaseHTMLParser', 'BCSParser']
