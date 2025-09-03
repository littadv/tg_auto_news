"""
Главный модуль tg_auto_news

Новая модульная архитектура с улучшенной структурой и документацией.
"""

import asyncio
import logging
from typing import List

# Импорты конфигурации
from config import Settings, ChannelConfig, ParserConfig

# Импорты утилит
from utils import (
    setup_logger, 
    HTTPClient, 
    MessageSender, 
    DeduplicationManager, 
    DateChecker,
    ErrorCallback
)

# Импорты парсеров
from parsers import TelegramParser, RSSParser
from parsers.html_parsers import BCSParser

# Импорты для обратной совместимости
from telethon import TelegramClient


class NewsBot:
    """
    Главный класс бота для парсинга новостей
    
    Управляет всеми парсерами и обеспечивает их координацию.
    """
    
    def __init__(self):
        """Инициализация бота"""
        # Загружаем конфигурацию
        self.settings = Settings()
        self.channel_config = ChannelConfig()
        self.parser_config = ParserConfig()
        
        # Настраиваем логирование
        self.logger = setup_logger('news_bot', self.settings.log_level)
        self.telethon_logger = setup_logger('telethon', self.settings.telethon_log_level)
        
        # Создаем компоненты
        self.http_client = HTTPClient(
            connect_timeout=self.settings.http_connect_timeout,
            read_timeout=self.settings.http_read_timeout,
            write_timeout=self.settings.http_write_timeout,
            pool_timeout=self.settings.http_pool_timeout,
            retries=self.settings.http_retries,
            verify_ssl=self.settings.http_verify_ssl
        )
        
        self.date_checker = DateChecker(logger=self.logger)
        self.deduplication_manager = DeduplicationManager(
            max_size=self.settings.duplicate_check_messages,
            check_chars=self.settings.duplicate_check_chars,
            logger=self.logger
        )
        
        # Telegram клиенты
        self.bot_client: TelegramClient = None
        self.message_sender: MessageSender = None
        self.error_callback: ErrorCallback = None
        
        # Парсеры
        self.parsers: List = []
        
        # Состояние
        self._running = False
    
    async def initialize(self):
        """Инициализация бота"""
        try:
            self.logger.info("Инициализация бота...")
            
            # Создаем HTTP клиент
            await self.http_client.get_client()
            
            # Создаем Telegram бот клиент
            self.bot_client = TelegramClient(
                self.settings.bot_session_name,
                self.settings.api_id,
                self.settings.api_hash,
                base_logger=self.telethon_logger
            )
            await self.bot_client.start(bot_token=self.settings.bot_token)
            
            # Создаем отправитель сообщений
            self.message_sender = MessageSender(
                bot_client=self.bot_client,
                target_chat_id=self.settings.target_chat_id,
                logger=self.logger
            )
            
            # Создаем обработчик ошибок
            self.error_callback = ErrorCallback(self.message_sender)
            
            # Загружаем историю для предотвращения дубликатов
            await self._load_history()
            
            # Создаем парсеры
            await self._create_parsers()
            
            self.logger.info("Бот успешно инициализирован")
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации бота: {e}")
            raise
    
    async def _load_history(self):
        """Загружает историю сообщений для предотвращения дубликатов"""
        try:
            # Создаем временный клиент для загрузки истории
            temp_client = TelegramClient(
                self.settings.telegram_session_name,
                self.settings.api_id,
                self.settings.api_hash
            )
            await temp_client.start()
            
            # Загружаем историю
            await self.deduplication_manager.load_history_from_telegram(
                client=temp_client,
                chat_id=self.settings.target_chat_id,
                amount_messages=self.settings.duplicate_check_messages
            )
            
            await temp_client.disconnect()
            
            self.logger.info("История сообщений загружена")
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки истории: {e}")
    
    async def _create_parsers(self):
        """Создает все парсеры"""
        try:
            # Telegram парсер
            if self.parser_config.is_parser_enabled('telegram'):
                telegram_channels = self.channel_config.get_enabled_telegram_channels()
                if telegram_channels:
                    telegram_parser = TelegramParser(
                        channels=telegram_channels,
                        settings=self.settings,
                        message_sender=self.message_sender,
                        deduplication_manager=self.deduplication_manager,
                        date_checker=self.date_checker,
                        logger=self.logger,
                        error_callback=self.error_callback
                    )
                    self.parsers.append(telegram_parser)
                    self.logger.info(f"Создан Telegram парсер для {len(telegram_channels)} каналов")
            
            # RSS парсер
            if self.parser_config.is_parser_enabled('rss'):
                rss_channels = self.channel_config.get_enabled_rss_channels()
                if rss_channels:
                    http_client = await self.http_client.get_client()
                    rss_parser = RSSParser(
                        channels=rss_channels,
                        settings=self.settings,
                        http_client=http_client,
                        message_sender=self.message_sender,
                        deduplication_manager=self.deduplication_manager,
                        date_checker=self.date_checker,
                        logger=self.logger,
                        error_callback=self.error_callback
                    )
                    self.parsers.append(rss_parser)
                    self.logger.info(f"Создан RSS парсер для {len(rss_channels)} каналов")
            
            # HTML парсеры
            if self.parser_config.is_parser_enabled('html'):
                html_channels = self.channel_config.get_enabled_html_channels()
                for channel_name, channel in html_channels.items():
                    if channel.parser_class == 'BCSParser':
                        http_client = await self.http_client.get_client()
                        bcs_parser = BCSParser(
                            settings=self.settings,
                            http_client=http_client,
                            message_sender=self.message_sender,
                            deduplication_manager=self.deduplication_manager,
                            date_checker=self.date_checker,
                            logger=self.logger,
                            error_callback=self.error_callback
                        )
                        self.parsers.append(bcs_parser)
                        self.logger.info(f"Создан BCS парсер")
            
            self.logger.info(f"Создано {len(self.parsers)} парсеров")
            
        except Exception as e:
            self.logger.error(f"Ошибка создания парсеров: {e}")
            raise
    
    async def start(self):
        """Запускает бота"""
        try:
            self.logger.info("Запуск бота...")
            
            await self.initialize()
            
            self._running = True
            
            # Запускаем все парсеры
            tasks = []
            for parser in self.parsers:
                task = asyncio.create_task(parser.start())
                tasks.append(task)
            
            if not tasks:
                self.logger.warning("Нет активных парсеров для запуска")
                return
            
            self.logger.info(f"Запущено {len(tasks)} парсеров")
            
            # Ждем завершения всех задач
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"Ошибка запуска бота: {e}")
            
            # Отправляем критическую ошибку
            if self.message_sender:
                error_msg = (
                    f"🚨 <b>Critical System Error</b>\n\n"
                    f"❌ <b>Component:</b> Main Application\n"
                    f"❌ <b>Error:</b> {type(e).__name__}\n"
                    f"📝 <b>Details:</b> {str(e)[:200]}"
                )
                await self.message_sender.send_error_message(error_msg)
            
            raise
    
    async def stop(self):
        """Останавливает бота"""
        try:
            self.logger.info("Остановка бота...")
            
            self._running = False
            
            # Останавливаем все парсеры
            for parser in self.parsers:
                try:
                    await parser.stop()
                except Exception as e:
                    self.logger.error(f"Ошибка остановки парсера {parser.name}: {e}")
            
            # Закрываем HTTP клиент
            await self.http_client.close()
            
            # Закрываем Telegram клиент
            if self.bot_client:
                await self.bot_client.disconnect()
            
            self.logger.info("Бот остановлен")
            
        except Exception as e:
            self.logger.error(f"Ошибка остановки бота: {e}")
    
    def get_status(self) -> dict:
        """
        Возвращает статус бота
        
        Returns:
            Словарь со статусом всех компонентов
        """
        return {
            'running': self._running,
            'parsers_count': len(self.parsers),
            'parsers_status': [parser.get_status() for parser in self.parsers],
            'channels_count': self.channel_config.get_enabled_channels_count(),
            'posted_count': self.deduplication_manager.get_posted_count()
        }


async def main():
    """Главная функция"""
    bot = NewsBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\nПолучен сигнал остановки...")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        await bot.stop()


if __name__ == "__main__":
    # Запускаем бота
    asyncio.run(main())
