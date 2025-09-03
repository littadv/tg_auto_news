"""
Парсеры для tg_auto_news

Этот пакет содержит все парсеры новостей:
- base_parser.py - базовый класс парсера
- telegram_parser.py - парсер Telegram каналов
- rss_parser.py - парсер RSS лент
- html_parsers/ - HTML парсеры для различных сайтов
"""

from .base_parser import BaseParser
from .telegram_parser import TelegramParser
from .rss_parser import RSSParser

__all__ = ['BaseParser', 'TelegramParser', 'RSSParser']
