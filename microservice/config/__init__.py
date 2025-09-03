"""
Конфигурационные модули для tg_auto_news

Этот пакет содержит все настройки приложения:
- settings.py - основные настройки
- channels.py - конфигурация каналов
- parsers.py - конфигурация парсеров
"""

from .settings import Settings
from .channels import ChannelConfig
from .parsers import ParserConfig

__all__ = ['Settings', 'ChannelConfig', 'ParserConfig']
