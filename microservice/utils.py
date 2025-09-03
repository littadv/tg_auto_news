import logging
import sys
import random
import httpx
from user_agents import user_agent_list  # список из значений user-agent
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # на старом питоне свалимся на UTC


_RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}

# Простые паттерны дат в тексте/ссылках
_RE_DDMMYYYY = re.compile(r"\b(?P<d>\d{1,2})[.\-/](?P<m>\d{1,2})[.\-/](?P<y>\d{4})(?:[ T](?P<h>\d{1,2}):(?P<min>\d{2})(?::(?P<s>\d{2}))?)?\b")
_RE_YYYYMMDD = re.compile(r"\b(?P<y>\d{4})[.\-/](?P<m>\d{1,2})[.\-/](?P<d>\d{1,2})(?:[ T](?P<h>\d{1,2}):(?P<min>\d{2})(?::(?P<s>\d{2}))?)?\b")
# Пример: "2 сентября 2025, 14:31" или "02 сент 2025 14:31"
_RE_RU_HUMAN = re.compile(
    r"\b(?P<d>\d{1,2})\s+(?P<mon>[А-Яа-яA-Za-z.]+)\s+(?P<y>\d{4})(?:[,\s]+(?P<h>\d{1,2}):(?P<min>\d{2})(?::(?P<s>\d{2}))?)?\b"
)
# Часто встречается в URL: /2025/09/02/
_RE_URL_YMD = re.compile(r"/(?P<y>20\d{2})/(?P<m>0?[1-9]|1[0-2])/(?P<d>0?[1-9]|[12]\d|3[01])(/|$)")


def _tz(moscow_default: bool = True):
    """Отдаем таймзону: Европа/Москва, если доступна, иначе UTC."""
    if ZoneInfo and moscow_default:
        try:
            return ZoneInfo("Europe/Moscow")
        except Exception:
            pass
    return timezone.utc


def parse_any_date(
    raw: str | None,
    fallback_url: str | None = None,
    logger=None,
) -> datetime | None:
    """
    Пытаемся распарсить дату из строки (RSS pubDate, текст, заголовок) или из URL.
    Возвращаем aware datetime (MSK если возможно, иначе UTC). Если не вышло — None.
    """
    if not raw:
        raw = ""

    text = raw.strip()

    # 1) RFC822 (типичный для RSS: "Mon, 02 Sep 2025 14:31:00 +0300")
    try:
        dt = parsedate_to_datetime(text)
        if dt is not None:
            # если на входе naive, подвяжем таймзону
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_tz())
            return dt
    except Exception:
        pass

    # 2) ISO-8601: 2025-09-02T14:31:00+03:00 или без TZ
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz())
        return dt
    except Exception:
        pass

    # 3) dd.mm.yyyy (с возможным временем)
    m = _RE_DDMMYYYY.search(text)
    if m:
        d = int(m.group("d")); mth = int(m.group("m")); y = int(m.group("y"))
        h = int(m.group("h") or 0); mi = int(m.group("min") or 0); s = int(m.group("s") or 0)
        try:
            return datetime(y, mth, d, h, mi, s, tzinfo=_tz())
        except Exception:
            pass

    # 4) yyyy-mm-dd (с возможным временем)
    m = _RE_YYYYMMDD.search(text)
    if m:
        y = int(m.group("y")); mth = int(m.group("m")); d = int(m.group("d"))
        h = int(m.group("h") or 0); mi = int(m.group("min") or 0); s = int(m.group("s") or 0)
        try:
            return datetime(y, mth, d, h, mi, s, tzinfo=_tz())
        except Exception:
            pass

    # 5) "2 сентября 2025, 14:31" (и англ)
    m = _RE_RU_HUMAN.search(text)
    if m:
        d = int(m.group("d")); y = int(m.group("y"))
        mon_raw = (m.group("mon") or "").strip(". ").lower()
        mth = _RU_MONTHS.get(mon_raw) or _EN_MONTHS.get(mon_raw)
        if mth:
            h = int(m.group("h") or 0); mi = int(m.group("min") or 0); s = int(m.group("s") or 0)
            try:
                return datetime(y, mth, d, h, mi, s, tzinfo=_tz())
            except Exception:
                pass

    # 6) Если в ссылке есть /YYYY/MM/DD/ — тоже ок
    if fallback_url:
        m = _RE_URL_YMD.search(fallback_url)
        if m:
            y = int(m.group("y")); mth = int(m.group("m")); d = int(m.group("d"))
            try:
                return datetime(y, mth, d, 0, 0, 0, tzinfo=_tz())
            except Exception:
                pass

    if logger:
        try:
            logger.debug(f"[date] не удалось распарсить дату из: '{text[:80]}' url={fallback_url}")
        except Exception:
            pass
    return None


def is_fresh(
    pub_dt: datetime | None,
    window_hours: int = 24,
    now: datetime | None = None,
) -> bool:
    """
    True, если публикация свежая (в пределах окна). Если pub_dt=None — False.
    """
    if pub_dt is None:
        return False
    if now is None:
        now = datetime.now(tz=pub_dt.tzinfo or _tz())
    return pub_dt <= now and (now - pub_dt) <= timedelta(hours=window_hours)


def check_date(
    text: str | None = None,
    link: str | None = None,
    raw_date_str: str | None = None,
    window_hours: int = 24,
    now: datetime | None = None,
    logger=None,
) -> bool:
    """
    Универсальная проверка даты для всех парсеров:
    - сначала пробуем взять explicit дату (raw_date_str, например pubDate из RSS),
    - если нет — парсим любую встреченную дату в тексте,
    - если нет — пробуем вытащить дату из URL (/YYYY/MM/DD/),
    - если даты нет вообще — возвращаем False (не публикуем, чтобы не тащить старье).
    """
    dt = None

    # явная дата имеет приоритет
    if raw_date_str:
        dt = parse_any_date(raw_date_str, fallback_url=link, logger=logger)

    # если явной нет — пробуем текст
    if dt is None and text:
        dt = parse_any_date(text, fallback_url=link, logger=logger)

    # если ничего не нашли — последний шанс из URL уже был в parse_any_date
    return is_fresh(dt, window_hours=window_hours, now=now) if dt else False

def create_logger(name, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s \n%(message)s \n' + '-'*30)
    handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


async def get_history(client, chat_id, n_test_chars=50, amount_messages=50):
    '''Забирает из канала уже опубликованные посты для того, чтобы их не дублировать'''
    history = []

    messages = await client.get_messages(chat_id, amount_messages)

    for message in messages:
        if message.raw_text is None:
            continue
        post = message.raw_text.split('\n')

        # Выкидывет источник и ссылку из поста, оставляя только текст
        text = '\n'.join(post[2:])

        history.append(text[:n_test_chars].strip())

    return history


def _accept_encoding_with_optional_brotli() -> str:
    # если установлен brotli/brotlicffi — можно смело просить br
    try:
        import brotlicffi  # noqa: F401
        return "gzip, deflate, br"
    except Exception:
        try:
            import brotli  # noqa: F401
            return "gzip, deflate, br"
        except Exception:
            return "gzip, deflate"

def browserish_headers(accept_xml: bool = False) -> dict:
    ua = random.choice(user_agent_list)
    accept = "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5" if accept_xml \
             else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    return {
        "User-Agent": ua,
        "Accept": accept,
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": _accept_encoding_with_optional_brotli(),  # br если умеем
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Upgrade-Insecure-Requests": "1",
    }

def random_user_agent_headers(accept_xml: bool = False) -> dict:
    return browserish_headers(accept_xml=accept_xml)

def random_user_agent_headers_xml() -> dict:
    """
    Узкоутилитарная шима: сразу заголовки под RSS.
    Удобно, если где-то в коде явно зовут «для xml».
    """
    return browserish_headers(accept_xml=True)

async def send_error_message(text, bot_token, chat_id, logger=None):
    '''Через бот отправляет сообщение напрямую в канал через telegram api'''
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
    except Exception as e:
        if logger is None:
            print(e)
        else:
            logger.error(e)

        return -1

    return response.status_code
