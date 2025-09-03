"""
Модуль HTTP клиента

Содержит настройки и утилиты для HTTP запросов.
"""

import httpx
import random
from typing import Dict, Optional
from user_agents import user_agent_list


class HTTPClient:
    """
    HTTP клиент для парсеров
    
    Обеспечивает единообразную настройку HTTP клиента для всех парсеров.
    """
    
    def __init__(
        self,
        connect_timeout: float = 30.0,
        read_timeout: float = 60.0,
        write_timeout: float = 30.0,
        pool_timeout: float = 60.0,
        retries: int = 5,
        verify_ssl: bool = False,
        http2: bool = True,
        follow_redirects: bool = True
    ):
        """
        Инициализация HTTP клиента
        
        Args:
            connect_timeout: Таймаут подключения
            read_timeout: Таймаут чтения
            write_timeout: Таймаут записи
            pool_timeout: Таймаут пула соединений
            retries: Количество повторных попыток
            verify_ssl: Проверять ли SSL сертификаты
            http2: Использовать ли HTTP/2
            follow_redirects: Следовать ли редиректам
        """
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.write_timeout = write_timeout
        self.pool_timeout = pool_timeout
        self.retries = retries
        self.verify_ssl = verify_ssl
        self.http2 = http2
        self.follow_redirects = follow_redirects
        
        self._client: Optional[httpx.AsyncClient] = None
    
    def create_client(self) -> httpx.AsyncClient:
        """
        Создает настроенный HTTP клиент
        
        Returns:
            Настроенный AsyncClient
        """
        transport = httpx.AsyncHTTPTransport(retries=self.retries)
        
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self.connect_timeout,
                read=self.read_timeout,
                write=self.write_timeout,
                pool=self.pool_timeout
            ),
            transport=transport,
            verify=self.verify_ssl,
            http2=self.http2,
            follow_redirects=self.follow_redirects
        )
        
        return client
    
    async def get_client(self) -> httpx.AsyncClient:
        """
        Возвращает HTTP клиент (создает если нужно)
        
        Returns:
            HTTP клиент
        """
        if self._client is None:
            self._client = self.create_client()
        return self._client
    
    async def close(self):
        """Закрывает HTTP клиент"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def get_browser_headers(accept_xml: bool = False) -> Dict[str, str]:
    """
    Возвращает заголовки браузера для HTTP запросов
    
    Args:
        accept_xml: Использовать ли заголовки для XML/RSS
        
    Returns:
        Словарь с заголовками
    """
    user_agent = random.choice(user_agent_list)
    
    if accept_xml:
        accept = (
            "application/rss+xml, application/xml;q=0.9, "
            "text/xml;q=0.8, */*;q=0.5"
        )
    else:
        accept = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "*/*;q=0.8"
        )
    
    return {
        "User-Agent": user_agent,
        "Accept": accept,
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": _get_accept_encoding(),
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Upgrade-Insecure-Requests": "1",
    }


def _get_accept_encoding() -> str:
    """
    Возвращает строку Accept-Encoding с поддержкой brotli если доступно
    
    Returns:
        Строка Accept-Encoding
    """
    try:
        import brotlicffi  # noqa: F401
        return "gzip, deflate, br"
    except ImportError:
        try:
            import brotli  # noqa: F401
            return "gzip, deflate, br"
        except ImportError:
            return "gzip, deflate"


# Функции для обратной совместимости
def browserish_headers(accept_xml: bool = False) -> Dict[str, str]:
    """Алиас для get_browser_headers"""
    return get_browser_headers(accept_xml)


def random_user_agent_headers(accept_xml: bool = False) -> Dict[str, str]:
    """Алиас для get_browser_headers"""
    return get_browser_headers(accept_xml)


def random_user_agent_headers_xml() -> Dict[str, str]:
    """Возвращает заголовки для XML запросов"""
    return get_browser_headers(accept_xml=True)
