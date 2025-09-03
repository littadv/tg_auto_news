"""
Парсер RSS лент

Парсит новости из RSS лент и отправляет их в целевой канал.
"""

import asyncio
import random
import logging
from typing import Dict, Optional, Callable, Awaitable
import httpx
import feedparser

from .base_parser import BaseParser
from config.channels import RSSChannel
from config.settings import Settings
from utils.http_client import get_browser_headers


class RSSParser(BaseParser):
    """
    Парсер для RSS лент
    
    Периодически проверяет RSS ленты и обрабатывает новые записи.
    """
    
    def __init__(
        self,
        channels: Dict[str, RSSChannel],
        settings: Settings,
        http_client: httpx.AsyncClient,
        message_sender,
        deduplication_manager,
        date_checker,
        logger: Optional[logging.Logger] = None,
        error_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ):
        """
        Инициализация RSS парсера
        
        Args:
            channels: Словарь RSS каналов для мониторинга
            settings: Настройки приложения
            http_client: HTTP клиент для запросов
            message_sender: Отправитель сообщений
            deduplication_manager: Менеджер дубликатов
            date_checker: Проверяльщик дат
            logger: Логгер
            error_callback: Функция для отправки ошибок
        """
        super().__init__(
            name="RSS Parser",
            message_sender=message_sender,
            deduplication_manager=deduplication_manager,
            date_checker=date_checker,
            logger=logger,
            error_callback=error_callback
        )
        
        self.channels = channels
        self.settings = settings
        self.http_client = http_client
        self._tasks = []
    
    async def start(self):
        """Запускает RSS парсер"""
        try:
            if self.logger:
                self.logger.info(f"Запуск RSS парсера для {len(self.channels)} каналов")
            
            self._running = True
            
            # Создаем задачи для каждого канала
            for channel_name, channel in self.channels.items():
                task = asyncio.create_task(
                    self._monitor_channel(channel_name, channel)
                )
                self._tasks.append(task)
            
            if self.logger:
                self.logger.info("RSS парсер успешно запущен")
            
            # Ждем завершения всех задач
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
        except Exception as e:
            self.increment_error_count()
            
            error_msg = (
                f"🚨 <b>RSS Parser Error</b>\n\n"
                f"❌ <b>Startup failed:</b> {type(e).__name__}\n"
                f"📝 <b>Details:</b> {str(e)[:200]}"
            )
            
            await self.send_error(error_msg)
            
            if self.logger:
                self.logger.error(f"Ошибка запуска RSS парсера: {e}")
            
            raise
    
    async def stop(self):
        """Останавливает RSS парсер"""
        try:
            self._running = False
            
            # Отменяем все задачи
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            
            # Ждем завершения задач
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
            
            self._tasks.clear()
            
            if self.logger:
                self.logger.info("RSS парсер остановлен")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка остановки RSS парсера: {e}")
    
    async def _monitor_channel(self, channel_name: str, channel: RSSChannel):
        """
        Мониторит RSS канал
        
        Args:
            channel_name: Имя канала
            channel: Конфигурация канала
        """
        while self._running:
            try:
                await self._fetch_and_process_channel(channel_name, channel)
                
                # Ждем перед следующим запросом
                await self.sleep_with_jitter(self.settings.request_timeout)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.increment_error_count()
                
                error_msg = (
                    f"🚨 <b>RSS Parser Error</b>\n\n"
                    f"❌ <b>Source:</b> {channel_name}\n"
                    f"❌ <b>Error:</b> {type(e).__name__}\n"
                    f"📝 <b>Details:</b> {str(e)[:200]}"
                )
                
                await self.send_error(error_msg)
                
                if self.logger:
                    self.logger.error(f"Ошибка мониторинга канала {channel_name}: {e}")
                
                # Ждем дольше при ошибке
                await self.sleep_with_jitter(self.settings.request_timeout * 2)
    
    async def _fetch_and_process_channel(self, channel_name: str, channel: RSSChannel):
        """
        Загружает и обрабатывает RSS канал
        
        Args:
            channel_name: Имя канала
            channel: Конфигурация канала
        """
        try:
            # Загружаем RSS ленту
            response = await self.http_client.get(
                channel.url,
                headers=get_browser_headers(accept_xml=True),
                follow_redirects=True
            )
            response.raise_for_status()
            
            # Парсим RSS
            feed = feedparser.parse(response.text)
            
            if not feed.entries:
                if self.logger:
                    self.logger.warning(f"Пустая RSS лента: {channel_name}")
                return
            
            # Обрабатываем записи
            processed_count = 0
            for entry in feed.entries[:20]:  # Ограничиваем количество
                try:
                    # Извлекаем данные записи
                    title = entry.get('title', '').strip()
                    summary = entry.get('summary', '').strip()
                    link = entry.get('link', '').strip()
                    pub_date = entry.get('published') or entry.get('pubDate')
                    
                    if not title:
                        continue
                    
                    # Обрабатываем новость
                    success = await self.process_news_item(
                        title=title,
                        content=summary,
                        link=link,
                        raw_date=pub_date,
                        source=channel_name
                    )
                    
                    if success:
                        processed_count += 1
                        
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Ошибка обработки записи RSS: {e}")
                    continue
            
            if self.logger and processed_count > 0:
                self.logger.info(f"Обработано {processed_count} новостей из {channel_name}")
                
        except httpx.ConnectTimeout:
            error_msg = (
                f"🚨 <b>RSS Parser Error</b>\n\n"
                f"❌ <b>Source:</b> {channel_name}\n"
                f"❌ <b>Error:</b> ConnectTimeout\n"
                f"📝 <b>Details:</b> Connection timeout"
            )
            await self.send_error(error_msg)
            
        except httpx.ReadTimeout:
            error_msg = (
                f"🚨 <b>RSS Parser Error</b>\n\n"
                f"❌ <b>Source:</b> {channel_name}\n"
                f"❌ <b>Error:</b> ReadTimeout\n"
                f"📝 <b>Details:</b> Read timeout"
            )
            await self.send_error(error_msg)
            
        except httpx.HTTPStatusError as e:
            error_msg = (
                f"🚨 <b>RSS Parser Error</b>\n\n"
                f"❌ <b>Source:</b> {channel_name}\n"
                f"❌ <b>Error:</b> HTTP {e.response.status_code}\n"
                f"📝 <b>Details:</b> {str(e)[:200]}"
            )
            await self.send_error(error_msg)
            
        except Exception as e:
            error_msg = (
                f"🚨 <b>RSS Parser Error</b>\n\n"
                f"❌ <b>Source:</b> {channel_name}\n"
                f"❌ <b>Error:</b> {type(e).__name__}\n"
                f"📝 <b>Details:</b> {str(e)[:200]}"
            )
            await self.send_error(error_msg)
    
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
        return list(self.channels.keys())


# Функция для обратной совместимости
async def rss_parser(
    httpx_client,
    source: str,
    rss_link: str,
    posted_q,
    n_test_chars: int = 50,
    timeout: int = 2,
    проверка_даты=None,
    send_message_func=None,
    error_callback=None
):
    """
    Функция для обратной совместимости со старым кодом
    
    Парсит RSS ленту в старом формате.
    """
    from collections import deque
    import feedparser
    from ..utils.http_client import get_browser_headers
    
    while True:
        try:
            response = await httpx_client.get(
                rss_link,
                headers=get_browser_headers(accept_xml=True),
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.ConnectTimeout as e:
            if error_callback:
                error_msg = f'🚨 <b>RSS Parser Error</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Error:</b> ConnectTimeout\n📝 <b>Details:</b> {str(e)[:200]}'
                await error_callback(error_msg)
            await asyncio.sleep(timeout*2 - random.uniform(0, 0.5))
            continue
        except httpx.ReadTimeout as e:
            if error_callback:
                error_msg = f'🚨 <b>RSS Parser Error</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Error:</b> ReadTimeout\n📝 <b>Details:</b> {str(e)[:200]}'
                await error_callback(error_msg)
            await asyncio.sleep(timeout*2 - random.uniform(0, 0.5))
            continue
        except httpx.HTTPStatusError as e:
            if error_callback:
                error_msg = f'🚨 <b>RSS Parser Error</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Error:</b> HTTP {e.response.status_code}\n📝 <b>Details:</b> {str(e)[:200]}'
                await error_callback(error_msg)
            await asyncio.sleep(timeout*2 - random.uniform(0, 0.5))
            continue
        except Exception as e:
            if error_callback:
                error_msg = f'🚨 <b>RSS Parser Error</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Error:</b> {type(e).__name__}\n📝 <b>Details:</b> {str(e)[:200]}'
                await error_callback(error_msg)
            await asyncio.sleep(timeout*2 - random.uniform(0, 0.5))
            continue

        try:
            feed = feedparser.parse(response.text)
            
            if not feed.entries:
                if error_callback:
                    error_msg = f'⚠️ <b>RSS Parser Warning</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Issue:</b> No entries found in RSS feed\n📝 <b>Response size:</b> {len(response.text)} bytes'
                    await error_callback(error_msg)
                await asyncio.sleep(timeout - random.uniform(0, 0.5))
                continue

        except Exception as e:
            if error_callback:
                error_msg = f'🚨 <b>RSS Parser Error</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Error:</b> Feed parsing failed\n📝 <b>Details:</b> {str(e)[:200]}'
                await error_callback(error_msg)
            await asyncio.sleep(timeout - random.uniform(0, 0.5))
            continue

        for entry in feed.entries[:20][::-1]:
            try:
                if 'summary' not in entry and 'title' not in entry:
                    continue

                summary = entry.get('summary', '')
                title = entry.get('title', '')
                link = entry.get('link', '')
                pub  = entry.get('published') or entry.get('pubDate')  # если есть

                news_text = f'{title}\n{summary}'

                # единая проверка свежести с обработкой ошибок
                try:
                    if not проверка_даты(text=news_text, link=link, raw_date_str=pub, window_hours=12):
                        continue
                except Exception as e:
                    if error_callback:
                        error_msg = f'🚨 <b>RSS Parser Error</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Error:</b> Date check failed\n📝 <b>Details:</b> {str(e)[:200]}'
                        await error_callback(error_msg)
                    continue

                head = news_text[:n_test_chars].strip()
                if head in posted_q:
                    continue

                post = f'<b>{source}</b>\n{link}\n{news_text}'

                if send_message_func is None:
                    print(post, '\n')
                else:
                    try:
                        await send_message_func(post)
                    except Exception as e:
                        if error_callback:
                            error_msg = f'🚨 <b>RSS Parser Error</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Error:</b> Send message failed\n📝 <b>Details:</b> {str(e)[:200]}'
                            await error_callback(error_msg)
                        continue

                posted_q.appendleft(head)

            except Exception as e:
                if error_callback:
                    error_msg = f'🚨 <b>RSS Parser Error</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Error:</b> Entry processing failed\n📝 <b>Details:</b> {str(e)[:200]}'
                    await error_callback(error_msg)
                continue

        await asyncio.sleep(timeout - random.uniform(0, 0.5))
