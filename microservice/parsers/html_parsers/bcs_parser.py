"""
Парсер для bcs-express.ru

Специализированный парсер для сайта bcs-express.ru.
"""

import asyncio
import random
import re
import logging
from typing import List, Tuple, Optional
import httpx

from .base_html import BaseHTMLParser
from config.settings import Settings
from utils.http_client import get_browser_headers


class BCSParser(BaseHTMLParser):
    """
    Парсер для bcs-express.ru
    
    Парсит новости с сайта bcs-express.ru через RSS и HTML.
    """
    
    # Конфигурация BCS парсера
    RSS_URLS = [
        "https://www.bcs-express.ru/news?format=rss",
        "https://bcs-express.ru/news?format=rss",
    ]
    
    SITE_ROOTS = [
        "https://www.bcs-express.ru", 
        "https://bcs-express.ru"
    ]
    
    HOMEPAGES = [root + "/" for root in SITE_ROOTS]
    
    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
        message_sender,
        deduplication_manager,
        date_checker,
        logger: Optional[logging.Logger] = None,
        error_callback=None
    ):
        """
        Инициализация BCS парсера
        
        Args:
            settings: Настройки приложения
            http_client: HTTP клиент
            message_sender: Отправитель сообщений
            deduplication_manager: Менеджер дубликатов
            date_checker: Проверяльщик дат
            logger: Логгер
            error_callback: Функция для отправки ошибок
        """
        super().__init__(
            name="BCS Parser",
            base_url="https://www.bcs-express.ru",
            message_sender=message_sender,
            deduplication_manager=deduplication_manager,
            date_checker=date_checker,
            logger=logger,
            error_callback=error_callback
        )
        
        self.settings = settings
        self.http_client = http_client
        self.source_name = "www.bcs-express.ru"
    
    async def start(self):
        """Запускает BCS парсер"""
        try:
            if self.logger:
                self.logger.info("Запуск BCS парсера")
            
            self._running = True
            
            # Основной цикл парсинга
            while self._running:
                try:
                    await self._parse_cycle()
                    
                    # Ждем перед следующим циклом
                    await self.sleep_with_jitter(self.settings.request_timeout)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.increment_error_count()
                    
                    error_msg = (
                        f"🚨 <b>BCS Parser Error</b>\n\n"
                        f"❌ <b>Source:</b> {self.source_name}\n"
                        f"❌ <b>Error:</b> {type(e).__name__}\n"
                        f"📝 <b>Details:</b> {str(e)[:200]}"
                    )
                    
                    await self.send_error(error_msg)
                    
                    if self.logger:
                        self.logger.error(f"Ошибка в цикле парсинга BCS: {e}")
                    
                    # Ждем дольше при ошибке
                    await self.sleep_with_jitter(self.settings.request_timeout * 2)
            
            if self.logger:
                self.logger.info("BCS парсер остановлен")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка запуска BCS парсера: {e}")
            raise
    
    async def stop(self):
        """Останавливает BCS парсер"""
        self._running = False
    
    async def _parse_cycle(self):
        """Выполняет один цикл парсинга"""
        try:
            # Парсим новости
            news_items = await self.parse_news_items(self.http_client)
            
            if not news_items:
                if self.logger:
                    self.logger.warning("Не найдено новостей в BCS")
                # Даем источнику "отдохнуть": не дергаем его хотя бы минуту
                await asyncio.sleep(max(60, int(self.settings.request_timeout)))
                return
            
            # Обрабатываем каждую новость
            processed_count = 0
            for title, link, pub_date in news_items:
                try:
                    success = await self.process_news_item(
                        title=title,
                        content="",  # Для BCS используем только заголовок
                        link=link,
                        raw_date=pub_date,
                        source=self.source_name
                    )
                    
                    if success:
                        processed_count += 1
                        
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Ошибка обработки новости BCS: {e}")
                    continue
            
            if self.logger and processed_count > 0:
                self.logger.info(f"Обработано {processed_count} новостей из BCS")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка цикла парсинга BCS: {e}")
            raise
    
    async def parse_news_items(self, http_client: httpx.AsyncClient) -> List[Tuple[str, str, Optional[str]]]:
        """
        Парсит новостные элементы с BCS сайта
        
        Args:
            http_client: HTTP клиент
            
        Returns:
            Список кортежей (заголовок, ссылка, дата)
        """
        items = []
        
        # Сначала пробуем RSS
        rss_items = await self._parse_rss_feeds(http_client)
        if rss_items:
            items = rss_items
        else:
            # Fallback на главную страницу
            items = await self._parse_homepage(http_client)
        
        return items
    
    async def _parse_rss_feeds(self, http_client: httpx.AsyncClient) -> List[Tuple[str, str, Optional[str]]]:
        """
        Парсит RSS ленты BCS
        
        Args:
            http_client: HTTP клиент
            
        Returns:
            Список новостей из RSS
        """
        for rss_url in self.RSS_URLS:
            try:
                # Подготавливаем заголовки
                headers = get_browser_headers(accept_xml=True)
                host_root = rss_url.split("/news", 1)[0]
                headers["Referer"] = host_root + "/"
                
                # Загружаем RSS
                response = await self.fetch_url(http_client, rss_url, headers)
                if not response:
                    continue
                
                # Парсим RSS
                items = self._parse_rss_xml(response.text, limit=12)
                if items:
                    if self.logger:
                        self.logger.info(f"Найдено {len(items)} новостей в RSS BCS")
                    return items
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Ошибка парсинга RSS BCS {rss_url}: {e}")
                continue
        
        return []
    
    def _parse_rss_xml(self, xml: str, limit: int = 12) -> List[Tuple[str, str, Optional[str]]]:
        """
        Парсит XML RSS ленты
        
        Args:
            xml: XML содержимое RSS
            limit: Максимальное количество элементов
            
        Returns:
            Список новостей
        """
        items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL | re.IGNORECASE)[:limit]
        result = []
        
        for chunk in items:
            # Извлекаем заголовок
            title_match = re.search(r"<title>(.*?)</title>", chunk, re.DOTALL | re.IGNORECASE)
            title = self.clean_html(title_match.group(1)) if title_match else ""
            
            # Извлекаем ссылку
            link_match = re.search(r"<link>(.*?)</link>", chunk, re.DOTALL | re.IGNORECASE)
            link = self.clean_html(link_match.group(1)) if link_match else self.SITE_ROOTS[0]
            
            # Извлекаем дату
            pub_match = re.search(r"<pubDate>(.*?)</pubDate>", chunk, re.DOTALL | re.IGNORECASE)
            pub_date = self.clean_html(pub_match.group(1)) if pub_match else None
            
            if title:
                result.append((title, link, pub_date))
        
        return result
    
    async def _parse_homepage(self, http_client: httpx.AsyncClient) -> List[Tuple[str, str, Optional[str]]]:
        """
        Парсит главную страницу BCS
        
        Args:
            http_client: HTTP клиент
            
        Returns:
            Список новостей с главной страницы
        """
        for site_root, homepage in zip(self.SITE_ROOTS, self.HOMEPAGES):
            try:
                # Подготавливаем заголовки
                headers = get_browser_headers(accept_xml=False)
                headers["Referer"] = site_root + "/"
                
                # Загружаем главную страницу
                response = await self.fetch_url(http_client, homepage, headers)
                if not response:
                    continue
                
                # Парсим заголовки
                titles = self.extract_titles_from_html(response.text, limit=10)
                if titles:
                    # Создаем новости из заголовков
                    items = [(title, site_root, None) for title in titles]
                    if self.logger:
                        self.logger.info(f"Найдено {len(items)} новостей на главной BCS")
                    return items
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Ошибка парсинга главной BCS {site_root}: {e}")
                continue
        
        return []


# Функция для обратной совместимости
async def bcs_parser(
    httpx_client: httpx.AsyncClient,
    posted_q,
    n_test_chars: int = 50,
    timeout: int = 2,
    проверка_даты=None,
    send_message_func=None,
    logger=None,
    error_callback=None,
):
    """
    Функция для обратной совместимости со старым кодом
    
    Парсит BCS сайт в старом формате.
    """
    import asyncio
    import random
    import re
    from collections import deque
    from typing import List, Tuple
    from ...utils.http_client import get_browser_headers
    from ...utils.date_checker import date_checker
    
    RSS_URLS = [
        "https://www.bcs-express.ru/news?format=rss",
        "https://bcs-express.ru/news?format=rss",
    ]
    SITE_ROOTS = ["https://www.bcs-express.ru", "https://bcs-express.ru"]
    HOMEPAGES = [r + "/" for r in SITE_ROOTS]
    
    def _log(logger, msg: str):
        (logger.info if logger else print)(msg)
    
    def _clean_html(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text or "").strip()
    
    def _dedupe_keep_order(items: List[str]) -> List[str]:
        seen, out = set(), []
        for x in items:
            if x not in seen:
                seen.add(x); out.append(x)
        return out
    
    async def _fetch(client: httpx.AsyncClient, url: str, headers: dict, logger) -> httpx.Response:
        _log(logger, f"[BCS] GET {url}")
        resp = await client.get(url, headers=headers, follow_redirects=True)
        resp.raise_for_status()
        return resp
    
    def _parse_rss(xml: str, limit: int = 12) -> List[Tuple[str, str, str | None]]:
        items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL | re.IGNORECASE)[:limit]
        out: List[Tuple[str, str, str | None]] = []
        for chunk in items:
            m_title = re.search(r"<title>(.*?)</title>", chunk, re.DOTALL | re.IGNORECASE)
            m_link  = re.search(r"<link>(.*?)</link>", chunk,   re.DOTALL | re.IGNORECASE)
            m_pub   = re.search(r"<pubDate>(.*?)</pubDate>", chunk, re.DOTALL | re.IGNORECASE)
            title = _clean_html(m_title.group(1)) if m_title else ""
            link  = _clean_html(m_link.group(1))  if m_link  else SITE_ROOTS[0]
            pub   = _clean_html(m_pub.group(1))   if m_pub   else None
            if title:
                out.append((title, link, pub))
        return out
    
    def _parse_homepage(html: str, site_root: str, limit: int = 10) -> List[Tuple[str, str]]:
        titles_raw = re.findall(r"<h[12-6][^>]*>(.*?)</h[12-6]>", html, re.DOTALL | re.IGNORECASE)
        titles = []
        for t in titles_raw:
            clean = _clean_html(t)
            if len(clean) >= 10 and not clean.lower().startswith(("подпис", "cookie", "политик")):
                titles.append(clean)
        titles = _dedupe_keep_order(titles)[:limit]

        links_raw = re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        links = []
        for href in links_raw:
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = site_root + href
            links.append(href)

        out: List[Tuple[str, str]] = []
        for i, title in enumerate(titles):
            link = links[i] if i < len(links) else site_root
            out.append((title, link))
        return out
    
    source = "www.bcs-express.ru"

    while True:
        try:
            h_xml = get_browser_headers(accept_xml=True)
            h_html = get_browser_headers(accept_xml=False)

            items: List[Tuple[str, str, str | None]] = []
            rss_last_err = None

            # 1) RSS
            for rss_url in RSS_URLS:
                try:
                    host_root = rss_url.split("/news", 1)[0]
                    h = dict(h_xml); h["Referer"] = host_root + "/"
                    resp = await _fetch(httpx_client, rss_url, h, logger)
                    xml = resp.text
                    _log(logger, f"[BCS] RSS HTTP {resp.status_code}, bytes={len(resp.content)}")
                    candidates = _parse_rss(xml, limit=12)
                    if candidates:
                        items = candidates
                        break
                except httpx.HTTPStatusError as e:
                    rss_last_err = e
                    code = e.response.status_code
                    _log(logger, f"[BCS] RSS try fail: {code} {e}")
                    if code in (403, 406):
                        await asyncio.sleep(0.2)
                        try:
                            alt = get_browser_headers(accept_xml=True)
                            alt["Referer"] = host_root + "/"
                            alt["Sec-Fetch-Site"] = "same-origin"
                            alt["Sec-Fetch-Mode"] = "no-cors"
                            resp = await _fetch(httpx_client, rss_url, alt, logger)
                            candidates = _parse_rss(resp.text, limit=12)
                            if candidates:
                                items = candidates
                                break
                        except Exception as e2:
                            rss_last_err = e2
                    await asyncio.sleep(0.25)
                except Exception as e:
                    rss_last_err = e
                    _log(logger, f"[BCS] RSS try fail: {type(e).__name__}: {e}")
                    await asyncio.sleep(0.25)

            # 2) Fallback на главную
            if not items:
                for site_root, home in zip(SITE_ROOTS, HOMEPAGES):
                    try:
                        h = dict(h_html); h["Referer"] = site_root + "/"
                        resp = await _fetch(httpx_client, home, h, logger)
                        html = resp.text
                        _log(logger, f"[BCS] HOME HTTP {resp.status_code}, bytes={len(resp.content)}")
                        hp = _parse_homepage(html, site_root, limit=10)
                        if hp:
                            items = [(t, l, None) for (t, l) in hp]
                            break
                    except Exception as e:
                        _log(logger, f"[BCS] HOME fail on {site_root}: {type(e).__name__}: {e}")
                        await asyncio.sleep(0.25)

                if not items and rss_last_err:
                    _log(logger, f"[BCS] RSS last error: {type(rss_last_err).__name__}: {rss_last_err}")

            # 3) Публикуем только свежее и без дублей
            for title, link, pub_date_str in items:
                try:
                    if not date_checker.check_news_date(text=title, link=link, raw_date_str=pub_date_str, window_hours=12, logger=logger):
                        continue
                    head = title[:n_test_chars].strip()
                    if head in posted_q:
                        _log(logger, f"[BCS] skip duplicate: {head}")
                        continue
                    post = f"<b>{source}</b>\n{link}\n{title}"
                    if send_message_func:
                        await send_message_func(post)
                    else:
                        _log(logger, post + "\n")
                    posted_q.appendleft(head)
                except Exception as e:
                    _log(logger, f"[BCS] item error: {type(e).__name__}: {e}")
                    continue

        except httpx.ConnectTimeout as e:
            _log(logger, f"[BCS] ConnectTimeout: {e}")
            if error_callback:
                error_msg = f'🚨 <b>BCS Parser Error</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Error:</b> ConnectTimeout\n📝 <b>Details:</b> {str(e)[:200]}'
                await error_callback(error_msg)
        except httpx.ReadTimeout as e:
            _log(logger, f"[BCS] ReadTimeout: {e}")
            if error_callback:
                error_msg = f'🚨 <b>BCS Parser Error</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Error:</b> ReadTimeout\n📝 <b>Details:</b> {str(e)[:200]}'
                await error_callback(error_msg)
        except httpx.HTTPStatusError as e:
            _log(logger, f"[BCS] HTTPStatusError: {e.response.status_code} {e}")
            if error_callback:
                error_msg = f'🚨 <b>BCS Parser Error</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Error:</b> HTTP {e.response.status_code}\n📝 <b>Details:</b> {str(e)[:200]}'
                await error_callback(error_msg)
        except Exception as e:
            _log(logger, f"[BCS] unexpected error: {type(e).__name__}: {e}")
            if error_callback:
                error_msg = f'🚨 <b>BCS Parser Error</b>\n\n❌ <b>Source:</b> {source}\n❌ <b>Error:</b> {type(e).__name__}\n📝 <b>Details:</b> {str(e)[:200]}'
                await error_callback(error_msg)

        await asyncio.sleep(max(0.5, timeout - random.uniform(0, 0.5)))
