"""
Модуль отправки сообщений

Содержит классы для отправки сообщений в Telegram канал.
"""

import httpx
import logging
from typing import Optional, Callable, Awaitable
from telethon import TelegramClient


class MessageSender:
    """
    Класс для отправки сообщений в Telegram канал
    
    Обеспечивает отправку как обычных новостей, так и сообщений об ошибках.
    """
    
    def __init__(
        self,
        bot_client: TelegramClient,
        target_chat_id: int,
        logger: Optional[logging.Logger] = None
    ):
        """
        Инициализация отправителя сообщений
        
        Args:
            bot_client: Telegram клиент для отправки сообщений
            target_chat_id: ID канала назначения
            logger: Логгер для записи операций
        """
        self.bot_client = bot_client
        self.target_chat_id = target_chat_id
        self.logger = logger
    
    async def send_news_message(self, text: str) -> bool:
        """
        Отправляет новость в канал
        
        Args:
            text: Текст новости
            
        Returns:
            True если сообщение отправлено успешно, False иначе
        """
        try:
            await self.bot_client.send_message(
                entity=self.target_chat_id,
                parse_mode='html',
                link_preview=False,
                message=text
            )
            
            if self.logger:
                self.logger.info(f"Новость отправлена: {text[:100]}...")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка отправки новости: {e}")
            return False
    
    async def send_error_message(self, error_text: str) -> bool:
        """
        Отправляет сообщение об ошибке в канал
        
        Args:
            error_text: Текст ошибки
            
        Returns:
            True если сообщение отправлено успешно, False иначе
        """
        try:
            await self.bot_client.send_message(
                entity=self.target_chat_id,
                parse_mode='html',
                link_preview=False,
                message=error_text
            )
            
            if self.logger:
                self.logger.error(f"Сообщение об ошибке отправлено: {error_text[:100]}...")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка отправки сообщения об ошибке: {e}")
            return False


class ErrorCallback:
    """
    Класс для обработки ошибок с отправкой в Telegram
    
    Предоставляет единообразный интерфейс для отправки ошибок.
    """
    
    def __init__(self, message_sender: MessageSender):
        """
        Инициализация обработчика ошибок
        
        Args:
            message_sender: Отправитель сообщений
        """
        self.message_sender = message_sender
    
    async def __call__(self, error_text: str):
        """
        Отправляет сообщение об ошибке
        
        Args:
            error_text: Текст ошибки
        """
        await self.message_sender.send_error_message(error_text)


# Функции для обратной совместимости
async def send_error_message(
    text: str, 
    bot_token: str, 
    chat_id: int, 
    logger: Optional[logging.Logger] = None
) -> int:
    """
    Отправляет сообщение об ошибке через Telegram API (для обратной совместимости)
    
    Args:
        text: Текст сообщения
        bot_token: Токен бота
        chat_id: ID чата
        logger: Логгер
        
    Returns:
        Код статуса ответа или -1 при ошибке
    """
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    
    params = {
        'text': text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "disable_notification": False,
        "reply_to_message_id": None,
        "chat_id": str(chat_id)
    }
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.status_code
            
    except Exception as e:
        if logger:
            logger.error(f"Ошибка отправки сообщения об ошибке: {e}")
        else:
            print(f"Ошибка отправки сообщения об ошибке: {e}")
        return -1
