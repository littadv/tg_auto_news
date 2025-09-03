"""
Базовый класс парсера

Содержит общую логику для всех парсеров новостей.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Callable, Awaitable, Any

from utils.date_checker import DateChecker
from utils.deduplication import DeduplicationManager
from utils.message_sender import MessageSender


class BaseParser(ABC):
    """
    Базовый класс для всех парсеров новостей
    
    Определяет общий интерфейс и функциональность для всех типов парсеров.
    """
    
    def __init__(
        self,
        name: str,
        message_sender: MessageSender,
        deduplication_manager: DeduplicationManager,
        date_checker: DateChecker,
        logger: Optional[logging.Logger] = None,
        error_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ):
        """
        Инициализация базового парсера
        
        Args:
            name: Имя парсера
            message_sender: Отправитель сообщений
            deduplication_manager: Менеджер дубликатов
            date_checker: Проверяльщик дат
            logger: Логгер
            error_callback: Функция для отправки ошибок
        """
        self.name = name
        self.message_sender = message_sender
        self.deduplication_manager = deduplication_manager
        self.date_checker = date_checker
        self.logger = logger
        self.error_callback = error_callback
        
        # Состояние парсера
        self._running = False
        self._error_count = 0
        self._max_errors = 10  # Максимум ошибок перед временным отключением
    
    @abstractmethod
    async def start(self):
        """
        Запускает парсер
        
        Должен быть реализован в наследующих классах.
        """
        pass
    
    @abstractmethod
    async def stop(self):
        """
        Останавливает парсер
        
        Должен быть реализован в наследующих классах.
        """
        pass
    
    async def send_error(self, error_message: str):
        """
        Отправляет сообщение об ошибке
        
        Args:
            error_message: Текст ошибки
        """
        if self.error_callback:
            try:
                await self.error_callback(error_message)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Ошибка отправки сообщения об ошибке: {e}")
    
    def is_running(self) -> bool:
        """
        Проверяет, запущен ли парсер
        
        Returns:
            True если парсер запущен
        """
        return self._running
    
    def increment_error_count(self):
        """Увеличивает счетчик ошибок"""
        self._error_count += 1
    
    def reset_error_count(self):
        """Сбрасывает счетчик ошибок"""
        self._error_count = 0
    
    def has_too_many_errors(self) -> bool:
        """
        Проверяет, слишком ли много ошибок
        
        Returns:
            True если ошибок слишком много
        """
        return self._error_count >= self._max_errors
    
    async def process_news_item(
        self,
        title: str,
        content: str,
        link: Optional[str] = None,
        raw_date: Optional[str] = None,
        source: Optional[str] = None
    ) -> bool:
        """
        Обрабатывает новостной элемент
        
        Выполняет проверку даты, дубликатов и отправку сообщения.
        
        Args:
            title: Заголовок новости
            content: Содержимое новости
            link: Ссылка на новость
            raw_date: Сырая дата новости
            source: Источник новости
            
        Returns:
            True если новость была обработана успешно
        """
        try:
            # Объединяем заголовок и содержимое
            full_text = f"{title}\n{content}"
            
            # Проверяем дубликаты
            if self.deduplication_manager.is_duplicate(full_text):
                if self.logger:
                    self.logger.debug(f"Пропускаем дубликат: {title[:50]}...")
                return False
            
            # Проверяем дату
            if not self.date_checker.check_news_date(
                text=full_text,
                link=link,
                raw_date_str=raw_date,
                window_hours=12,
                strict_today=True
            ):
                if self.logger:
                    self.logger.debug(f"Пропускаем старую новость: {title[:50]}...")
                return False
            
            # Формируем сообщение для отправки
            if source:
                message = f"<b>{source}</b>\n{link or ''}\n{full_text}"
            else:
                message = f"<b>{self.name}</b>\n{link or ''}\n{full_text}"
            
            # Отправляем сообщение
            success = await self.message_sender.send_news_message(message)
            
            if success:
                # Отмечаем как опубликованную
                self.deduplication_manager.mark_as_posted(full_text)
                self.reset_error_count()
                
                if self.logger:
                    self.logger.info(f"Новость опубликована: {title[:50]}...")
                
                return True
            else:
                if self.logger:
                    self.logger.error(f"Не удалось отправить новость: {title[:50]}...")
                return False
                
        except Exception as e:
            self.increment_error_count()
            
            error_msg = (
                f"🚨 <b>{self.name} Parser Error</b>\n\n"
                f"❌ <b>Error:</b> News processing failed\n"
                f"📝 <b>Details:</b> {str(e)[:200]}"
            )
            
            await self.send_error(error_msg)
            
            if self.logger:
                self.logger.error(f"Ошибка обработки новости: {e}")
            
            return False
    
    async def sleep_with_jitter(self, base_timeout: int, jitter: float = 0.5):
        """
        Засыпает на случайное время с базовым таймаутом
        
        Args:
            base_timeout: Базовый таймаут в секундах
            jitter: Разброс времени (0.0 - 1.0)
        """
        import random
        sleep_time = base_timeout - random.uniform(0, jitter)
        await asyncio.sleep(max(0.1, sleep_time))
    
    def get_status(self) -> dict:
        """
        Возвращает статус парсера
        
        Returns:
            Словарь со статусом парсера
        """
        return {
            'name': self.name,
            'running': self._running,
            'error_count': self._error_count,
            'max_errors': self._max_errors,
            'has_too_many_errors': self.has_too_many_errors(),
            'posted_count': self.deduplication_manager.get_posted_count()
        }
