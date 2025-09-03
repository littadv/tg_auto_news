"""
Основные настройки приложения

Содержит все глобальные настройки, которые используются во всем приложении.
"""

import logging
from typing import Optional
from dataclasses import dataclass


@dataclass
class Settings:
    """
    Основные настройки приложения
    
    Содержит все глобальные параметры для работы парсеров новостей.
    """
    
    # === Telegram API настройки ===
    api_id: int = 22611766
    api_hash: str = "f579a247ce7dafdacdc7dfb69b51bd8c"
    bot_token: str = "8189849152:AAGIgkmnCT1rfzTtZlP038hJq1gUBWRuIRI"
    
    # === Канал назначения ===
    target_chat_id: int = -1002985288432
    
    # === Настройки парсинга ===
    # Количество первых символов для проверки дубликатов
    duplicate_check_chars: int = 50
    
    # Количество сообщений для проверки дубликатов
    duplicate_check_messages: int = 50
    
    # Интервал между запросами (секунды)
    request_timeout: int = 2
    
    # === HTTP клиент настройки ===
    # Таймауты для HTTP запросов
    http_connect_timeout: float = 30.0
    http_read_timeout: float = 60.0
    http_write_timeout: float = 30.0
    http_pool_timeout: float = 60.0
    
    # Количество повторных попыток
    http_retries: int = 5
    
    # Отключение SSL проверки для проблемных сайтов
    http_verify_ssl: bool = False
    
    # === Логирование ===
    log_level: int = logging.INFO
    telethon_log_level: int = logging.ERROR
    
    # === Проверка дат ===
    # Окно свежести новостей (часы)
    date_check_window_hours: int = 12
    
    # === Сессии ===
    telegram_session_name: str = 'gazp'
    bot_session_name: str = 'bot'
    
    def __post_init__(self):
        """Валидация настроек после инициализации"""
        if not self.api_id or not self.api_hash:
            raise ValueError("API ID и API Hash обязательны")
        
        if not self.bot_token:
            raise ValueError("Bot token обязателен")
        
        if not self.target_chat_id:
            raise ValueError("Target chat ID обязателен")


# Глобальный экземпляр настроек
settings = Settings()
