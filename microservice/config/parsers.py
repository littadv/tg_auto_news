"""
Конфигурация парсеров

Содержит настройки для всех типов парсеров:
- Telegram парсер
- RSS парсер  
- HTML парсеры
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ParserSettings:
    """
    Базовые настройки парсера
    
    Attributes:
        enabled: Включен ли парсер
        timeout: Таймаут между запросами (секунды)
        max_retries: Максимальное количество повторных попыток
        error_threshold: Порог ошибок для временного отключения
    """
    enabled: bool = True
    timeout: int = 2
    max_retries: int = 3
    error_threshold: int = 10


@dataclass
class TelegramParserSettings(ParserSettings):
    """
    Настройки Telegram парсера
    
    Attributes:
        session_name: Имя сессии для Telegram клиента
        check_duplicates: Проверять ли дубликаты
        date_check_enabled: Включена ли проверка дат
    """
    session_name: str = 'gazp'
    check_duplicates: bool = True
    date_check_enabled: bool = True


@dataclass
class RSSParserSettings(ParserSettings):
    """
    Настройки RSS парсера
    
    Attributes:
        max_entries: Максимальное количество записей для обработки
        check_duplicates: Проверять ли дубликаты
        date_check_enabled: Включена ли проверка дат
        follow_redirects: Следовать ли редиректам
    """
    max_entries: int = 20
    check_duplicates: bool = True
    date_check_enabled: bool = True
    follow_redirects: bool = True


@dataclass
class HTMLParserSettings(ParserSettings):
    """
    Настройки HTML парсера
    
    Attributes:
        max_items: Максимальное количество элементов для обработки
        check_duplicates: Проверять ли дубликаты
        date_check_enabled: Включена ли проверка дат
        user_agent_rotation: Ротация User-Agent
        respect_robots_txt: Соблюдать ли robots.txt
    """
    max_items: int = 10
    check_duplicates: bool = True
    date_check_enabled: bool = True
    user_agent_rotation: bool = True
    respect_robots_txt: bool = False


class ParserConfig:
    """
    Конфигурация всех парсеров
    
    Содержит настройки для всех типов парсеров.
    """
    
    def __init__(self):
        """Инициализация конфигурации парсеров"""
        self._telegram_settings = TelegramParserSettings()
        self._rss_settings = RSSParserSettings()
        self._html_settings = HTMLParserSettings()
        
        # Специфичные настройки для HTML парсеров
        self._html_parser_specific: Dict[str, Dict[str, Any]] = {
            'BCSParser': {
                'rss_urls': [
                    "https://www.bcs-express.ru/news?format=rss",
                    "https://bcs-express.ru/news?format=rss",
                ],
                'site_roots': [
                    "https://www.bcs-express.ru", 
                    "https://bcs-express.ru"
                ],
                'fallback_to_homepage': True,
                'max_rss_items': 12,
                'max_homepage_items': 10,
            }
        }
    
    # === Telegram парсер ===
    
    def get_telegram_settings(self) -> TelegramParserSettings:
        """Возвращает настройки Telegram парсера"""
        return self._telegram_settings
    
    def update_telegram_settings(self, **kwargs):
        """Обновляет настройки Telegram парсера"""
        for key, value in kwargs.items():
            if hasattr(self._telegram_settings, key):
                setattr(self._telegram_settings, key, value)
    
    # === RSS парсер ===
    
    def get_rss_settings(self) -> RSSParserSettings:
        """Возвращает настройки RSS парсера"""
        return self._rss_settings
    
    def update_rss_settings(self, **kwargs):
        """Обновляет настройки RSS парсера"""
        for key, value in kwargs.items():
            if hasattr(self._rss_settings, key):
                setattr(self._rss_settings, key, value)
    
    # === HTML парсеры ===
    
    def get_html_settings(self) -> HTMLParserSettings:
        """Возвращает общие настройки HTML парсеров"""
        return self._html_settings
    
    def update_html_settings(self, **kwargs):
        """Обновляет общие настройки HTML парсеров"""
        for key, value in kwargs.items():
            if hasattr(self._html_settings, key):
                setattr(self._html_settings, key, value)
    
    def get_html_parser_specific_settings(self, parser_name: str) -> Dict[str, Any]:
        """
        Возвращает специфичные настройки для конкретного HTML парсера
        
        Args:
            parser_name: Имя парсера (например, 'BCSParser')
            
        Returns:
            Словарь с настройками парсера
        """
        return self._html_parser_specific.get(parser_name, {}).copy()
    
    def update_html_parser_specific_settings(self, parser_name: str, settings: Dict[str, Any]):
        """
        Обновляет специфичные настройки для конкретного HTML парсера
        
        Args:
            parser_name: Имя парсера
            settings: Новые настройки
        """
        if parser_name not in self._html_parser_specific:
            self._html_parser_specific[parser_name] = {}
        
        self._html_parser_specific[parser_name].update(settings)
    
    # === Общие методы ===
    
    def is_parser_enabled(self, parser_type: str) -> bool:
        """
        Проверяет, включен ли парсер
        
        Args:
            parser_type: Тип парсера ('telegram', 'rss', 'html')
            
        Returns:
            True если парсер включен
        """
        if parser_type == 'telegram':
            return self._telegram_settings.enabled
        elif parser_type == 'rss':
            return self._rss_settings.enabled
        elif parser_type == 'html':
            return self._html_settings.enabled
        else:
            return False
    
    def get_parser_timeout(self, parser_type: str) -> int:
        """
        Возвращает таймаут для парсера
        
        Args:
            parser_type: Тип парсера ('telegram', 'rss', 'html')
            
        Returns:
            Таймаут в секундах
        """
        if parser_type == 'telegram':
            return self._telegram_settings.timeout
        elif parser_type == 'rss':
            return self._rss_settings.timeout
        elif parser_type == 'html':
            return self._html_settings.timeout
        else:
            return 2  # По умолчанию
    
    def get_all_enabled_parsers(self) -> list[str]:
        """Возвращает список всех включенных парсеров"""
        enabled = []
        if self._telegram_settings.enabled:
            enabled.append('telegram')
        if self._rss_settings.enabled:
            enabled.append('rss')
        if self._html_settings.enabled:
            enabled.append('html')
        return enabled


# Глобальный экземпляр конфигурации парсеров
parser_config = ParserConfig()
