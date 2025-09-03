"""
Модуль проверки дат новостей

Содержит логику для проверки свежести новостей и фильтрации по датам.
"""

import re
import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Union

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


class DateChecker:
    """
    Класс для проверки дат новостей
    
    Обеспечивает универсальную проверку свежести новостей из различных источников.
    """
    
    # Словари для парсинга месяцев
    _RU_MONTHS = {
        "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
        "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    }
    
    _EN_MONTHS = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, 
        "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    
    # Регулярные выражения для парсинга дат
    _RE_DDMMYYYY = re.compile(
        r"\b(?P<d>\d{1,2})[.\-/](?P<m>\d{1,2})[.\-/](?P<y>\d{4})"
        r"(?:[ T](?P<h>\d{1,2}):(?P<min>\d{2})(?::(?P<s>\d{2}))?)?\b"
    )
    
    _RE_YYYYMMDD = re.compile(
        r"\b(?P<y>\d{4})[.\-/](?P<m>\d{1,2})[.\-/](?P<d>\d{1,2})"
        r"(?:[ T](?P<h>\d{1,2}):(?P<min>\d{2})(?::(?P<s>\d{2}))?)?\b"
    )
    
    _RE_RU_HUMAN = re.compile(
        r"\b(?P<d>\d{1,2})\s+(?P<mon>[А-Яа-яA-Za-z.]+)\s+(?P<y>\d{4})"
        r"(?:[,\s]+(?P<h>\d{1,2}):(?P<min>\d{2})(?::(?P<s>\d{2}))?)?\b"
    )
    
    _RE_URL_YMD = re.compile(
        r"/(?P<y>20\d{2})/(?P<m>0?[1-9]|1[0-2])/(?P<d>0?[1-9]|[12]\d|3[01])(/|$)"
    )
    # Дата в URL в формате DD/MM/YYYY (например, .../31/08/2025/...)
    _RE_URL_DMY = re.compile(
        r"/(?P<d>0?[1-9]|[12]\d|3[01])/(?P<m>0?[1-9]|1[0-2])/(?P<y>20\d{2})(/|$)"
    )
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Инициализация проверяльщика дат
        
        Args:
            logger: Логгер для записи отладочной информации
        """
        self.logger = logger
    
    def _get_timezone(self, moscow_default: bool = True) -> timezone:
        """
        Возвращает таймзону
        
        Args:
            moscow_default: Использовать ли московское время по умолчанию
            
        Returns:
            Объект таймзоны
        """
        if ZoneInfo and moscow_default:
            try:
                return ZoneInfo("Europe/Moscow")
            except Exception:
                pass
        return timezone.utc
    
    def parse_date(
        self, 
        raw_date: Optional[str], 
        fallback_url: Optional[str] = None
    ) -> Optional[datetime]:
        """
        Парсит дату из строки или URL
        
        Поддерживает различные форматы дат:
        - RFC822 (RSS): "Mon, 02 Sep 2024 14:31:00 +0300"
        - ISO-8601: "2024-09-02T14:31:00+03:00"
        - DD.MM.YYYY: "02.09.2024 14:31"
        - YYYY-MM-DD: "2024-09-02 14:31"
        - Русский: "2 сентября 2024, 14:31"
        - URL: "/2024/09/02/news"
        
        Args:
            raw_date: Строка с датой
            fallback_url: URL для извлечения даты, если raw_date не содержит дату
            
        Returns:
            Объект datetime или None, если дату не удалось распарсить
        """
        if not raw_date:
            raw_date = ""
        
        text = raw_date.strip()
        
        # 1) RFC822 (типичный для RSS)
        try:
            dt = parsedate_to_datetime(text)
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=self._get_timezone())
                return dt
        except Exception:
            pass
        
        # 2) ISO-8601
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=self._get_timezone())
            return dt
        except Exception:
            pass
        
        # 3) DD.MM.YYYY
        match = self._RE_DDMMYYYY.search(text)
        if match:
            try:
                day = int(match.group("d"))
                month = int(match.group("m"))
                year = int(match.group("y"))
                hour = int(match.group("h") or 0)
                minute = int(match.group("min") or 0)
                second = int(match.group("s") or 0)
                
                return datetime(
                    year, month, day, hour, minute, second, 
                    tzinfo=self._get_timezone()
                )
            except (ValueError, TypeError):
                pass
        
        # 4) YYYY-MM-DD
        match = self._RE_YYYYMMDD.search(text)
        if match:
            try:
                year = int(match.group("y"))
                month = int(match.group("m"))
                day = int(match.group("d"))
                hour = int(match.group("h") or 0)
                minute = int(match.group("min") or 0)
                second = int(match.group("s") or 0)
                
                return datetime(
                    year, month, day, hour, minute, second, 
                    tzinfo=self._get_timezone()
                )
            except (ValueError, TypeError):
                pass
        
        # 5) Русский формат: "2 сентября 2024, 14:31"
        match = self._RE_RU_HUMAN.search(text)
        if match:
            try:
                day = int(match.group("d"))
                year = int(match.group("y"))
                month_raw = (match.group("mon") or "").strip(". ").lower()
                
                month = self._RU_MONTHS.get(month_raw) or self._EN_MONTHS.get(month_raw)
                if month:
                    hour = int(match.group("h") or 0)
                    minute = int(match.group("min") or 0)
                    second = int(match.group("s") or 0)
                    
                    return datetime(
                        year, month, day, hour, minute, second, 
                        tzinfo=self._get_timezone()
                    )
            except (ValueError, TypeError):
                pass
        
        # 6) Дата из URL (YYYY/MM/DD)
        if fallback_url:
            match = self._RE_URL_YMD.search(fallback_url)
            if match:
                try:
                    year = int(match.group("y"))
                    month = int(match.group("m"))
                    day = int(match.group("d"))
                    
                    return datetime(
                        year, month, day, 0, 0, 0, 
                        tzinfo=self._get_timezone()
                    )
                except (ValueError, TypeError):
                    pass
        
        # 7) Дата из URL (DD/MM/YYYY)
        if fallback_url:
            match = self._RE_URL_DMY.search(fallback_url)
            if match:
                try:
                    day = int(match.group("d"))
                    month = int(match.group("m"))
                    year = int(match.group("y"))
                    
                    return datetime(
                        year, month, day, 0, 0, 0,
                        tzinfo=self._get_timezone()
                    )
                except (ValueError, TypeError):
                    pass
        
        # Логируем неудачную попытку парсинга
        if self.logger:
            self.logger.debug(
                f"Не удалось распарсить дату из: '{text[:80]}' "
                f"url={fallback_url}"
            )
        
        return None
    
    def is_fresh(
        self, 
        pub_date: Optional[datetime], 
        window_hours: int = 24,
        now: Optional[datetime] = None
    ) -> bool:
        """
        Проверяет, свежая ли новость
        
        Args:
            pub_date: Дата публикации новости
            window_hours: Окно свежести в часах
            now: Текущее время (для тестирования)
            
        Returns:
            True если новость свежая, False иначе
        """
        if pub_date is None:
            return False
        
        if now is None:
            now = datetime.now(tz=pub_date.tzinfo or self._get_timezone())
        
        return pub_date <= now and (now - pub_date) <= timedelta(hours=window_hours)
    
    def is_today(self, pub_date: Optional[datetime]) -> bool:
        """
        Проверяет, опубликована ли новость сегодня
        
        Args:
            pub_date: Дата публикации новости
            
        Returns:
            True если новость сегодняшняя, False иначе
        """
        if pub_date is None:
            return False
        
        # Приводим обе даты к одной таймзоне
        tz = pub_date.tzinfo or self._get_timezone()
        now_local = datetime.now(tz=tz)
        news_date = pub_date.astimezone(tz).date()
        today = now_local.date()
        return news_date == today
    
    def check_news_date(
        self,
        text: Optional[str] = None,
        link: Optional[str] = None,
        raw_date_str: Optional[str] = None,
        window_hours: int = 12,
        strict_today: bool = True
    ) -> bool:
        """
        Универсальная проверка даты новости
        
        Проверяет новость на свежесть с учетом различных источников дат.
        
        Args:
            text: Текст новости для поиска даты
            link: Ссылка на новость для извлечения даты из URL
            raw_date_str: Явная дата (например, из RSS pubDate)
            window_hours: Окно свежести в часах
            strict_today: Строгая проверка на сегодняшнюю дату
            
        Returns:
            True если новость должна быть опубликована, False иначе
        """
        parsed_date = None
        
        # Приоритет: явная дата > текст > URL
        if raw_date_str:
            parsed_date = self.parse_date(raw_date_str, fallback_url=link)
        
        if parsed_date is None and text:
            parsed_date = self.parse_date(text, fallback_url=link)
        
        if parsed_date is None:
            # Если дату не удалось извлечь, не публикуем
            if self.logger:
                self.logger.debug("Дата не найдена в новости, пропускаем")
            return False
        
        # Проверяем свежесть
        if not self.is_fresh(parsed_date, window_hours=window_hours):
            if self.logger:
                self.logger.info(f"Новость не свежая: {parsed_date}")
            return False
        
        # Строгая проверка на сегодняшнюю дату
        if strict_today and not self.is_today(parsed_date):
            if self.logger:
                self.logger.info(f"Пропускаем вчерашнюю новость: {parsed_date.date()}")
            return False
        
        if self.logger:
            self.logger.info(
                f"Проверка даты: {parsed_date.date()}, "
                f"сегодня: {datetime.now().date()}, "
                f"свежая: {self.is_fresh(parsed_date, window_hours)}"
            )
        
        return True


# Глобальный экземпляр для обратной совместимости
date_checker = DateChecker()
