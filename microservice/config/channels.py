"""
Конфигурация каналов для парсинга

Содержит настройки всех каналов-источников новостей:
- Telegram каналы
- RSS ленты
- HTML сайты
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TelegramChannel:
    """
    Конфигурация Telegram канала
    
    Attributes:
        channel_id: ID канала в Telegram
        url: URL канала (https://t.me/channel_name)
        name: Человекочитаемое имя канала
        enabled: Включен ли канал для парсинга
    """
    channel_id: int
    url: str
    name: str
    enabled: bool = True


@dataclass
class RSSChannel:
    """
    Конфигурация RSS канала
    
    Attributes:
        name: Имя источника
        url: URL RSS ленты
        enabled: Включен ли канал для парсинга
    """
    name: str
    url: str
    enabled: bool = True


@dataclass
class HTMLChannel:
    """
    Конфигурация HTML сайта
    
    Attributes:
        name: Имя источника
        base_url: Базовый URL сайта
        parser_class: Класс парсера для этого сайта
        enabled: Включен ли канал для парсинга
    """
    name: str
    base_url: str
    parser_class: str
    enabled: bool = True


class ChannelConfig:
    """
    Конфигурация всех каналов
    
    Содержит настройки всех источников новостей.
    """
    
    def __init__(self):
        """Инициализация конфигурации каналов"""
        self._telegram_channels: Dict[int, TelegramChannel] = {}
        self._rss_channels: Dict[str, RSSChannel] = {}
        self._html_channels: Dict[str, HTMLChannel] = {}
        
        # Загружаем предустановленные каналы
        self._load_default_channels()
    
    def _load_default_channels(self):
        """Загружает предустановленные каналы"""
        
        # Telegram каналы
        telegram_channels = [
            TelegramChannel(
                channel_id=1099860397,
                url='https://t.me/moscowach',
                name='Moscowach',
                enabled=True
            ),
            TelegramChannel(
                channel_id=1428717522,
                url='https://t.me/gazprom',
                name='Gazprom',
                enabled=True
            ),
            # TelegramChannel(
            #     channel_id=1001029560,
            #     url='https://t.me/bcs_express',
            #     name='BCS Express',
            #     enabled=False  # Отключен
            # ),
        ]
        
        for channel in telegram_channels:
            self._telegram_channels[channel.channel_id] = channel
        
        # RSS каналы
        rss_channels = [
            RSSChannel(
                name='www.rbc.ru',
                url='https://rssexport.rbc.ru/rbcnews/news/30/full.rss',
                enabled=True
            ),
        ]
        
        for channel in rss_channels:
            self._rss_channels[channel.name] = channel
        
        # HTML каналы
        html_channels = [
            HTMLChannel(
                name='www.bcs-express.ru',
                base_url='https://www.bcs-express.ru',
                parser_class='BCSParser',
                enabled=True
            ),
        ]
        
        for channel in html_channels:
            self._html_channels[channel.name] = channel
    
    # === Telegram каналы ===
    
    def get_telegram_channels(self) -> Dict[int, TelegramChannel]:
        """Возвращает все Telegram каналы"""
        return self._telegram_channels.copy()
    
    def get_enabled_telegram_channels(self) -> Dict[int, TelegramChannel]:
        """Возвращает только включенные Telegram каналы"""
        return {
            channel_id: channel 
            for channel_id, channel in self._telegram_channels.items()
            if channel.enabled
        }
    
    def get_telegram_channel_urls(self) -> List[str]:
        """Возвращает список URL включенных Telegram каналов"""
        return [
            channel.url 
            for channel in self.get_enabled_telegram_channels().values()
        ]
    
    def add_telegram_channel(self, channel: TelegramChannel):
        """Добавляет новый Telegram канал"""
        self._telegram_channels[channel.channel_id] = channel
    
    def remove_telegram_channel(self, channel_id: int):
        """Удаляет Telegram канал"""
        if channel_id in self._telegram_channels:
            del self._telegram_channels[channel_id]
    
    # === RSS каналы ===
    
    def get_rss_channels(self) -> Dict[str, RSSChannel]:
        """Возвращает все RSS каналы"""
        return self._rss_channels.copy()
    
    def get_enabled_rss_channels(self) -> Dict[str, RSSChannel]:
        """Возвращает только включенные RSS каналы"""
        return {
            name: channel 
            for name, channel in self._rss_channels.items()
            if channel.enabled
        }
    
    def add_rss_channel(self, channel: RSSChannel):
        """Добавляет новый RSS канал"""
        self._rss_channels[channel.name] = channel
    
    def remove_rss_channel(self, name: str):
        """Удаляет RSS канал"""
        if name in self._rss_channels:
            del self._rss_channels[name]
    
    # === HTML каналы ===
    
    def get_html_channels(self) -> Dict[str, HTMLChannel]:
        """Возвращает все HTML каналы"""
        return self._html_channels.copy()
    
    def get_enabled_html_channels(self) -> Dict[str, HTMLChannel]:
        """Возвращает только включенные HTML каналы"""
        return {
            name: channel 
            for name, channel in self._html_channels.items()
            if channel.enabled
        }
    
    def add_html_channel(self, channel: HTMLChannel):
        """Добавляет новый HTML канал"""
        self._html_channels[channel.name] = channel
    
    def remove_html_channel(self, name: str):
        """Удаляет HTML канал"""
        if name in self._html_channels:
            del self._html_channels[name]
    
    # === Общие методы ===
    
    def get_all_channels_count(self) -> int:
        """Возвращает общее количество каналов"""
        return (
            len(self._telegram_channels) + 
            len(self._rss_channels) + 
            len(self._html_channels)
        )
    
    def get_enabled_channels_count(self) -> int:
        """Возвращает количество включенных каналов"""
        return (
            len(self.get_enabled_telegram_channels()) + 
            len(self.get_enabled_rss_channels()) + 
            len(self.get_enabled_html_channels())
        )


# Глобальный экземпляр конфигурации каналов
channel_config = ChannelConfig()
