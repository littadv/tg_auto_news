"""
Базовый HTML парсер

Содержит общую логику для парсинга HTML сайтов.
"""

import re
import logging
from typing import List, Tuple, Optional, Dict, Any
from abc import abstractmethod
import httpx

from ..base_parser import BaseParser
from utils.http_client import get_browser_headers


class BaseHTMLParser(BaseParser):
    """
    Базовый класс для HTML парсеров
    
    Предоставляет общую функциональность для парсинга HTML сайтов.
    """
    
    def __init__(
        self,
        name: str,
        base_url: str,
        message_sender,
        deduplication_manager,
        date_checker,
        logger: Optional[logging.Logger] = None,
        error_callback=None
    ):
        """
        Инициализация базового HTML парсера
        
        Args:
            name: Имя парсера
            base_url: Базовый URL сайта
            message_sender: Отправитель сообщений
            deduplication_manager: Менеджер дубликатов
            date_checker: Проверяльщик дат
            logger: Логгер
            error_callback: Функция для отправки ошибок
        """
        super().__init__(
            name=name,
            message_sender=message_sender,
            deduplication_manager=deduplication_manager,
            date_checker=date_checker,
            logger=logger,
            error_callback=error_callback
        )
        
        self.base_url = base_url
    
    def clean_html(self, text: str) -> str:
        """
        Очищает HTML теги из текста
        
        Args:
            text: Текст с HTML тегами
            
        Returns:
            Очищенный текст
        """
        if not text:
            return ""
        
        # Удаляем HTML теги
        clean_text = re.sub(r"<[^>]+>", "", text)
        
        # Нормализуем пробелы
        clean_text = re.sub(r"\s+", " ", clean_text)
        
        return clean_text.strip()
    
    def dedupe_keep_order(self, items: List[str]) -> List[str]:
        """
        Удаляет дубликаты, сохраняя порядок
        
        Args:
            items: Список элементов
            
        Returns:
            Список без дубликатов
        """
        seen = set()
        result = []
        
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        
        return result
    
    async def fetch_url(
        self,
        http_client: httpx.AsyncClient,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Optional[httpx.Response]:
        """
        Загружает URL с обработкой ошибок
        
        Args:
            http_client: HTTP клиент
            url: URL для загрузки
            headers: Заголовки запроса
            
        Returns:
            Ответ сервера или None при ошибке
        """
        try:
            if headers is None:
                headers = get_browser_headers()
            
            if self.logger:
                self.logger.debug(f"Загрузка URL: {url}")
            
            response = await http_client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            
            if self.logger:
                self.logger.debug(f"URL загружен: {url}, статус: {response.status_code}, размер: {len(response.content)}")
            
            return response
            
        except httpx.ConnectTimeout as e:
            if self.logger:
                self.logger.error(f"Таймаут подключения для {url}: {e}")
            return None
            
        except httpx.ReadTimeout as e:
            if self.logger:
                self.logger.error(f"Таймаут чтения для {url}: {e}")
            return None
            
        except httpx.HTTPStatusError as e:
            if self.logger:
                self.logger.error(f"HTTP ошибка для {url}: {e.response.status_code}")
            return None
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка загрузки {url}: {e}")
            return None
    
    def extract_titles_from_html(self, html: str, limit: int = 10) -> List[str]:
        """
        Извлекает заголовки из HTML
        
        Args:
            html: HTML код
            limit: Максимальное количество заголовков
            
        Returns:
            Список заголовков
        """
        # Ищем заголовки h1-h6
        title_pattern = r"<h[1-6][^>]*>(.*?)</h[1-6]>"
        matches = re.findall(title_pattern, html, re.DOTALL | re.IGNORECASE)
        
        titles = []
        for match in matches:
            clean_title = self.clean_html(match)
            
            # Фильтруем заголовки
            if (len(clean_title) >= 10 and 
                not clean_title.lower().startswith(("подпис", "cookie", "политик", "меню"))):
                titles.append(clean_title)
        
        # Удаляем дубликаты и ограничиваем количество
        titles = self.dedupe_keep_order(titles)[:limit]
        
        return titles
    
    def extract_links_from_html(self, html: str, base_url: str) -> List[str]:
        """
        Извлекает ссылки из HTML
        
        Args:
            html: HTML код
            base_url: Базовый URL для относительных ссылок
            
        Returns:
            Список ссылок
        """
        # Ищем ссылки
        link_pattern = r'<a[^>]+href=["\']([^"\']+)["\']'
        matches = re.findall(link_pattern, html, re.IGNORECASE)
        
        links = []
        for href in matches:
            # Обрабатываем относительные ссылки
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = base_url + href
            elif not href.startswith(("http://", "https://")):
                href = base_url + "/" + href
            
            links.append(href)
        
        return links
    
    def extract_dates_from_text(self, text: str) -> List[str]:
        """
        Извлекает даты из текста
        
        Args:
            text: Текст для поиска дат
            
        Returns:
            Список найденных дат
        """
        # Паттерны для поиска дат
        date_patterns = [
            r"\b\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4}\b",  # DD.MM.YYYY
            r"\b\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}\b",  # YYYY-MM-DD
            r"\b\d{1,2}\s+[а-яё]+\s+\d{4}\b",        # "2 сентября 2024"
        ]
        
        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)
        
        return dates
    
    @abstractmethod
    async def parse_news_items(self, http_client: httpx.AsyncClient) -> List[Tuple[str, str, Optional[str]]]:
        """
        Парсит новостные элементы с сайта
        
        Должен быть реализован в наследующих классах.
        
        Args:
            http_client: HTTP клиент
            
        Returns:
            Список кортежей (заголовок, ссылка, дата)
        """
        pass
    
    async def start(self):
        """Запускает HTML парсер"""
        # Базовый HTML парсер не имеет собственного цикла
        # Он должен быть запущен извне
        pass
    
    async def stop(self):
        """Останавливает HTML парсер"""
        # Базовый HTML парсер не имеет собственного цикла
        pass
