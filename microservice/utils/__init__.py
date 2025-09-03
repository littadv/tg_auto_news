"""
Утилиты для tg_auto_news

Этот пакет содержит вспомогательные модули:
- date_checker.py - проверка дат новостей
- logger.py - настройка логирования
- http_client.py - HTTP клиент
- message_sender.py - отправка сообщений
- deduplication.py - проверка дубликатов
"""

from .date_checker import DateChecker
from .logger import setup_logger
from .http_client import HTTPClient
from .message_sender import MessageSender, ErrorCallback
from .deduplication import DeduplicationManager

__all__ = [
    'DateChecker', 
    'setup_logger', 
    'HTTPClient', 
    'MessageSender', 
    'ErrorCallback',
    'DeduplicationManager'
]
