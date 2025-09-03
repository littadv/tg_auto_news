"""
Парсер Telegram каналов

Парсит новости из Telegram каналов и отправляет их в целевой канал.
"""

import logging
from typing import Dict, Optional, Callable, Awaitable
from telethon import TelegramClient, events

from .base_parser import BaseParser
from config.channels import TelegramChannel
from config.settings import Settings


class TelegramParser(BaseParser):
    """
    Парсер для Telegram каналов
    
    Мониторит указанные Telegram каналы и пересылает новые сообщения.
    """
    
    def __init__(
        self,
        channels: Dict[int, TelegramChannel],
        settings: Settings,
        message_sender,
        deduplication_manager,
        date_checker,
        logger: Optional[logging.Logger] = None,
        error_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ):
        """
        Инициализация Telegram парсера
        
        Args:
            channels: Словарь каналов для мониторинга
            settings: Настройки приложения
            message_sender: Отправитель сообщений
            deduplication_manager: Менеджер дубликатов
            date_checker: Проверяльщик дат
            logger: Логгер
            error_callback: Функция для отправки ошибок
        """
        super().__init__(
            name="Telegram Parser",
            message_sender=message_sender,
            deduplication_manager=deduplication_manager,
            date_checker=date_checker,
            logger=logger,
            error_callback=error_callback
        )
        
        self.channels = channels
        self.settings = settings
        self.client: Optional[TelegramClient] = None
        
        # Создаем словарь для быстрого поиска каналов по ID
        self._channel_lookup = {channel_id: channel for channel_id, channel in channels.items()}
    
    async def start(self):
        """Запускает Telegram парсер"""
        try:
            if self.logger:
                self.logger.info(f"Запуск Telegram парсера для {len(self.channels)} каналов")
            
            # Создаем Telegram клиент
            self.client = TelegramClient(
                self.settings.telegram_session_name,
                self.settings.api_id,
                self.settings.api_hash
            )
            
            # Запускаем клиент
            await self.client.start()
            
            # Получаем список URL каналов для мониторинга
            channel_urls = [channel.url for channel in self.channels.values()]
            
            # Регистрируем обработчик новых сообщений
            @self.client.on(events.NewMessage(chats=channel_urls))
            async def handler(event):
                await self._handle_new_message(event)
            
            self._running = True
            
            if self.logger:
                self.logger.info("Telegram парсер успешно запущен")
            
            # Запускаем клиент до отключения
            await self.client.run_until_disconnected()
            
        except Exception as e:
            self.increment_error_count()
            
            error_msg = (
                f"🚨 <b>Telegram Parser Error</b>\n\n"
                f"❌ <b>Connection failed:</b> {type(e).__name__}\n"
                f"📝 <b>Details:</b> {str(e)[:200]}"
            )
            
            await self.send_error(error_msg)
            
            if self.logger:
                self.logger.error(f"Ошибка запуска Telegram парсера: {e}")
            
            raise
    
    async def stop(self):
        """Останавливает Telegram парсер"""
        try:
            self._running = False
            
            if self.client:
                await self.client.disconnect()
                self.client = None
            
            if self.logger:
                self.logger.info("Telegram парсер остановлен")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка остановки Telegram парсера: {e}")
    
    async def _handle_new_message(self, event):
        """
        Обрабатывает новое сообщение из канала
        
        Args:
            event: Событие нового сообщения
        """
        try:
            # Проверяем, что сообщение не пустое
            if not event.raw_text or event.raw_text.strip() == '':
                return
            
            # Извлекаем текст новости (первые две строки)
            news_lines = event.raw_text.split('\n')
            news_text = ' '.join(news_lines[:2])
            
            # Получаем информацию о канале
            try:
                channel_id = event.message.peer_id.channel_id
                channel = self._channel_lookup[channel_id]
                channel_name = f"@{channel.name}"
                message_link = f"{channel.url}/{event.message.id}"
            except KeyError:
                # Канал не найден в конфигурации
                error_msg = (
                    f"🚨 <b>Telegram Parser Error</b>\n\n"
                    f"❌ <b>Channel ID not found:</b> {event.message.peer_id.channel_id}\n"
                    f"📝 <b>Available channels:</b> {list(self.channels.keys())}"
                )
                await self.send_error(error_msg)
                return
            
            # Обрабатываем новость
            success = await self.process_news_item(
                title=news_text,
                content="",  # Для Telegram используем только заголовок
                link=message_link,
                source=channel_name
            )
            
            if not success and self.logger:
                self.logger.debug(f"Новость не была обработана: {news_text[:50]}...")
                
        except Exception as e:
            self.increment_error_count()
            
            error_msg = (
                f"🚨 <b>Telegram Parser Error</b>\n\n"
                f"❌ <b>Handler error:</b> {type(e).__name__}\n"
                f"📝 <b>Details:</b> {str(e)[:200]}"
            )
            
            await self.send_error(error_msg)
            
            if self.logger:
                self.logger.error(f"Ошибка обработки сообщения: {e}")
    
    def get_channel_count(self) -> int:
        """
        Возвращает количество отслеживаемых каналов
        
        Returns:
            Количество каналов
        """
        return len(self.channels)
    
    def get_channel_names(self) -> list[str]:
        """
        Возвращает список имен отслеживаемых каналов
        
        Returns:
            Список имен каналов
        """
        return [channel.name for channel in self.channels.values()]


# Функция для обратной совместимости
def telegram_parser(
    session: str,
    api_id: int,
    api_hash: str,
    telegram_channels: Dict[int, str],
    posted_q,
    n_test_chars: int = 50,
    проверка_даты=None,
    send_message_func=None,
    loop=None,
    error_callback=None
):
    """
    Функция для обратной совместимости со старым кодом
    
    Создает и возвращает Telegram клиент в старом формате.
    """
    from collections import deque
    from telethon import TelegramClient, events
    
    # Создаем клиент
    client = TelegramClient(session, api_id, api_hash, loop=loop)
    client.start()
    
    # Ссылки на телеграм каналы
    telegram_channels_links = list(telegram_channels.values())
    
    @client.on(events.NewMessage(chats=telegram_channels_links))
    async def handler(event):
        """Забирает посты из телеграм каналов и посылает их в наш канал"""
        try:
            if event.raw_text == '':
                return

            news_text = ' '.join(event.raw_text.split('\n')[:2])

            # Проверка даты с обработкой ошибок
            if not (проверка_даты is None):
                try:
                    if not проверка_даты(news_text):
                        return
                except Exception as e:
                    if error_callback:
                        error_msg = f'🚨 <b>Telegram Parser Error</b>\n\n❌ <b>Date check failed:</b> {type(e).__name__}\n📝 <b>Details:</b> {str(e)[:200]}'
                        await error_callback(error_msg)
                    return

            head = news_text[:n_test_chars].strip()

            if head in posted_q:
                return

            try:
                source = telegram_channels[event.message.peer_id.channel_id]
                link = f'{source}/{event.message.id}'
                channel = '@' + source.split('/')[-1]
            except KeyError as e:
                if error_callback:
                    error_msg = f'🚨 <b>Telegram Parser Error</b>\n\n❌ <b>Channel ID not found:</b> {event.message.peer_id.channel_id}\n📝 <b>Available channels:</b> {list(telegram_channels.keys())}'
                    await error_callback(error_msg)
                return

            post = f'<b>{channel}</b>\n{link}\n{news_text}'

            if send_message_func is None:
                print(post, '\n')
            else:
                try:
                    await send_message_func(post)
                except Exception as e:
                    if error_callback:
                        error_msg = f'🚨 <b>Telegram Parser Error</b>\n\n❌ <b>Send message failed:</b> {type(e).__name__}\n📝 <b>Details:</b> {str(e)[:200]}'
                        await error_callback(error_msg)
                    return

            posted_q.appendleft(head)

        except Exception as e:
            if error_callback:
                error_msg = f'🚨 <b>Telegram Parser Error</b>\n\n❌ <b>Handler error:</b> {type(e).__name__}\n📝 <b>Details:</b> {str(e)[:200]}'
                await error_callback(error_msg)

    return client
