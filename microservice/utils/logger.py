"""
Модуль настройки логирования

Содержит функции для настройки и создания логгеров.
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str, 
    level: int = logging.INFO,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Создает и настраивает логгер
    
    Args:
        name: Имя логгера
        level: Уровень логирования
        format_string: Кастомный формат строки
        
    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    
    # Избегаем дублирования обработчиков
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Формат по умолчанию
    if format_string is None:
        format_string = (
            '%(asctime)s - %(name)s - %(levelname)s \n'
            '%(message)s \n' + '-' * 30
        )
    
    formatter = logging.Formatter(format_string)
    
    # Обработчик для вывода в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


def create_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Создает логгер (для обратной совместимости)
    
    Args:
        name: Имя логгера
        level: Уровень логирования
        
    Returns:
        Настроенный логгер
    """
    return setup_logger(name, level)
