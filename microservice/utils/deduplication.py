"""
Модуль проверки дубликатов

Содержит логику для предотвращения публикации дублирующихся новостей.
"""

import logging
from collections import deque
from typing import Set, List, Optional
from telethon import TelegramClient


class DeduplicationManager:
    """
    Менеджер для проверки дубликатов новостей
    
    Отслеживает уже опубликованные новости и предотвращает дублирование.
    """
    
    def __init__(
        self,
        max_size: int = 50,
        check_chars: int = 50,
        logger: Optional[logging.Logger] = None
    ):
        """
        Инициализация менеджера дубликатов
        
        Args:
            max_size: Максимальный размер очереди дубликатов
            check_chars: Количество символов для проверки дубликатов
            logger: Логгер для записи операций
        """
        self.max_size = max_size
        self.check_chars = check_chars
        self.logger = logger
        
        # Очередь для хранения отпечатков уже опубликованных новостей
        self._posted_queue: deque = deque(maxlen=max_size)
        
        # Множество для быстрой проверки дубликатов
        self._posted_set: Set[str] = set()
    
    def _create_fingerprint(self, text: str) -> str:
        """
        Создает отпечаток новости для проверки дубликатов
        
        Args:
            text: Текст новости
            
        Returns:
            Отпечаток новости
        """
        # Берем первые N символов и нормализуем
        fingerprint = text[:self.check_chars].strip()
        
        # Убираем лишние пробелы и приводим к нижнему регистру
        fingerprint = ' '.join(fingerprint.split()).lower()
        
        return fingerprint
    
    def is_duplicate(self, text: str) -> bool:
        """
        Проверяет, является ли новость дубликатом
        
        Args:
            text: Текст новости
            
        Returns:
            True если новость уже была опубликована, False иначе
        """
        fingerprint = self._create_fingerprint(text)
        
        if fingerprint in self._posted_set:
            if self.logger:
                self.logger.debug(f"Найден дубликат: {fingerprint}")
            return True
        
        return False
    
    def mark_as_posted(self, text: str):
        """
        Отмечает новость как опубликованную
        
        Args:
            text: Текст новости
        """
        fingerprint = self._create_fingerprint(text)
        
        # Добавляем в очередь и множество
        self._posted_queue.appendleft(fingerprint)
        self._posted_set.add(fingerprint)
        
        # Удаляем старые записи из множества, если очередь переполнилась
        if len(self._posted_queue) == self.max_size:
            # Удаляем последний элемент из множества
            old_fingerprint = self._posted_queue[-1]
            self._posted_set.discard(old_fingerprint)
        
        if self.logger:
            self.logger.debug(f"Новость отмечена как опубликованная: {fingerprint}")
    
    def add_fingerprints(self, fingerprints: List[str]):
        """
        Добавляет список отпечатков в очередь дубликатов
        
        Args:
            fingerprints: Список отпечатков новостей
        """
        for fingerprint in fingerprints:
            if fingerprint not in self._posted_set:
                self._posted_queue.appendleft(fingerprint)
                self._posted_set.add(fingerprint)
        
        # Очищаем старые записи если нужно
        while len(self._posted_queue) > self.max_size:
            old_fingerprint = self._posted_queue.pop()
            self._posted_set.discard(old_fingerprint)
        
        if self.logger:
            self.logger.info(f"Добавлено {len(fingerprints)} отпечатков в очередь дубликатов")
    
    def get_posted_count(self) -> int:
        """
        Возвращает количество отслеживаемых новостей
        
        Returns:
            Количество новостей в очереди
        """
        return len(self._posted_queue)
    
    def clear(self):
        """Очищает очередь дубликатов"""
        self._posted_queue.clear()
        self._posted_set.clear()
        
        if self.logger:
            self.logger.info("Очередь дубликатов очищена")
    
    async def load_history_from_telegram(
        self,
        client: TelegramClient,
        chat_id: int,
        amount_messages: int = 50
    ):
        """
        Загружает историю сообщений из Telegram канала для предотвращения дубликатов
        
        Args:
            client: Telegram клиент
            chat_id: ID канала
            amount_messages: Количество сообщений для загрузки
        """
        try:
            messages = await client.get_messages(chat_id, amount_messages)
            fingerprints = []
            
            for message in messages:
                if message.raw_text is None:
                    continue
                
                # Извлекаем текст новости (убираем источник и ссылку)
                post_lines = message.raw_text.split('\n')
                if len(post_lines) >= 3:
                    # Берем только текст новости (пропускаем источник и ссылку)
                    news_text = '\n'.join(post_lines[2:])
                    fingerprint = self._create_fingerprint(news_text)
                    fingerprints.append(fingerprint)
            
            self.add_fingerprints(fingerprints)
            
            if self.logger:
                self.logger.info(
                    f"Загружено {len(fingerprints)} сообщений из истории канала"
                )
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка загрузки истории из Telegram: {e}")


# Функция для обратной совместимости
async def get_history(
    client: TelegramClient,
    chat_id: int,
    n_test_chars: int = 50,
    amount_messages: int = 50
) -> List[str]:
    """
    Загружает историю сообщений из канала (для обратной совместимости)
    
    Args:
        client: Telegram клиент
        chat_id: ID канала
        n_test_chars: Количество символов для проверки дубликатов
        amount_messages: Количество сообщений для загрузки
        
    Returns:
        Список отпечатков сообщений
    """
    try:
        messages = await client.get_messages(chat_id, amount_messages)
        history = []
        
        for message in messages:
            if message.raw_text is None:
                continue
            
            # Извлекаем текст новости
            post_lines = message.raw_text.split('\n')
            if len(post_lines) >= 3:
                # Берем только текст новости (пропускаем источник и ссылку)
                news_text = '\n'.join(post_lines[2:])
                fingerprint = news_text[:n_test_chars].strip()
                history.append(fingerprint)
        
        return history
        
    except Exception as e:
        print(f"Ошибка загрузки истории: {e}")
        return []
