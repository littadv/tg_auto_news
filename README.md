# TG Auto News Bot

Автоматический бот для парсинга новостей из Telegram, RSS и HTML-сайтов и публикации их в Telegram-канал. Проект построен на модульной архитектуре, легко поддерживается и расширяется.

---

## 1) Быстрый старт

1. Клонируйте репозиторий и перейдите в каталог:
```bash
git clone https://github.com/littadv/tg_auto_news.git
cd tg_auto_news
```
2. Установите зависимости:
```bash
pip install -r requirements.txt
```
3. Настройте `auto_pars_bot/microservice/config/settings.py`:
```python
api_id = "YOUR_API_ID"
api_hash = "YOUR_API_HASH"
bot_token = "YOUR_BOT_TOKEN"
# Целевой канал/чат для публикации
target_chat_id = -1001234567890
```
4. Запустите приложение:
```bash
python auto_pars_bot/microservice/main.py
```

---

## 2) Полная структура проекта

```
auto_pars_bot/
├── microservice/
│   ├── main.py                 # Главный модуль и класс NewsBot
│   │                           # Оркестрация, жизненный цикл, создание парсеров
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py         # Settings: API-ключи, логирование, таймауты, дедупликация
│   │   ├── channels.py         # ChannelConfig: Telegram/RSS/HTML источники
│   │   └── parsers.py          # ParserConfig: включение/настройка парсеров
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py           # setup_logger / create_logger
│   │   ├── http_client.py      # HTTPClient, get_browser_headers, aliasы
│   │   ├── message_sender.py   # MessageSender, ErrorCallback, send_error_message()
│   │   ├── deduplication.py    # DeduplicationManager: очередь отпечатков
│   │   └── date_checker.py     # DateChecker: парсинг/валидация дат, "только сегодня"
│   └── parsers/
│       ├── __init__.py         # Экспорты парсеров
│       ├── base_parser.py      # База для всех парсеров (общая логика)
│       ├── telegram_parser.py  # Телеграм-парсер (Telethon events)
│       ├── rss_parser.py       # RSS-парсер (httpx + feedparser)
│       └── html_parsers/
│           ├── __init__.py
│           ├── base_html.py    # База для HTML-парсеров: fetch/очистка/извлечения
│           └── bcs_parser.py   # Пример HTML/RSS парсера: bcs-express.ru
└── requirements.txt            # Зависимости
```

---

## 3) Жизненный цикл и взаимодействия

- `main.py / NewsBot`
  - Инициализация: Settings → логгеры → HTTPClient → TelegramClient → MessageSender → DeduplicationManager → DateChecker
  - Загрузка истории (`DeduplicationManager.load_history_from_telegram`) для первичного заполнения очереди отпечатков
  - Создание и запуск парсеров (Telegram, RSS, HTML)
  - Обработка критических ошибок и корректная остановка

Поток данных:
```
Источник → Парсер → DateChecker → DeduplicationManager → MessageSender → Telegram канал
```

Обработка ошибок:
```
Исключение → Лог + ErrorCallback → MessageSender.send_error_message → Сообщение в канал
```

---

## 4) Конфигурация (что и где настраивать)

- `config/settings.py` — глобальные параметры:
  - Telegram API: `api_id`, `api_hash`, `bot_token`, сессии (`telegram_session_name`, `bot_session_name`)
  - Канал назначения: `target_chat_id`
  - HTTP: `http_connect_timeout`, `http_read_timeout`, `http_write_timeout`, `http_pool_timeout`, `http_retries`, `http_verify_ssl`
  - Логирование: `log_level`, `telethon_log_level`
  - Дедупликация: `duplicate_check_messages`, `duplicate_check_chars`
  - Проверка дат: `date_check_window_hours` (окно свежести в часах)

- `config/channels.py` — источники:
  - Telegram: `TelegramChannel(channel_id, url, name, enabled)`
  - RSS: `RSSChannel(name, url, enabled)`
  - HTML: `HTMLChannel(name, base_url, parser_class, enabled)`

- `config/parsers.py` — включение/настройка парсеров:
  - `ParserConfig.is_parser_enabled('telegram'|'rss'|'html')`
  - Специфика HTML-парсеров (пример `BCSParser`): RSS-ленты, корни сайта, лимиты

---

## 5) Основные утилиты и их поведение

- `utils/logger.py`
  - `setup_logger(name, level, format_string=None)` — единый формат логов во всем приложении

- `utils/http_client.py`
  - `HTTPClient` создает общий `httpx.AsyncClient` с таймаутами, ретраями, HTTP/2, опцией SSL
  - `get_browser_headers(accept_xml=False)` — рандомный User-Agent + заголовки как у браузера

- `utils/message_sender.py`
  - `MessageSender.send_news_message(text)` — публикация новости в таргет-канал
  - `MessageSender.send_error_message(text)` — отправка ошибки в канал
  - `ErrorCallback(message_sender)` — удобный класс-коллбек для передачи в парсеры

- `utils/deduplication.py` (очередь/стек публикаций)
  - Хранит отпечатки уже отправленных новостей:
    - `_posted_queue: deque(maxlen=max_size)` — фиксированный буфер
    - `_posted_set: set` — быстрая проверка наличия отпечатка
  - Отпечаток = первые `check_chars` символов текста (нормализованный регистр и пробелы)
  - `is_duplicate(text)` — проверка дубликата за O(1)
  - `mark_as_posted(text)` — добавить отпечаток (и удалить самый старый при переполнении)
  - `load_history_from_telegram(client, chat_id, amount_messages)` — инициализирует очередь отпечатками из истории канала

- `utils/date_checker.py` (строгий дата-чек)
  - `parse_date(raw_date, fallback_url)` — поддержка RFC822/ISO/DD.MM.YYYY/YYYY-MM-DD/«2 сентября 2024»/дата из URL (YYYY/MM/DD и DD/MM/YYYY)
  - `is_fresh(pub_date, window_hours)` — свежесть в окне часов
  - `is_today(pub_date)` — «только сегодня» с учетом таймзоны
  - `check_news_date(text, link, raw_date_str, window_hours=12, strict_today=True)` — единая точка решения публиковать или нет

---

## 6) Базовый парсер и общая логика

- `parsers/base_parser.py` — все парсеры наследуют этот класс
  - Содержит общее состояние: `_running`, `_error_count`, `_max_errors`
  - Отправка ошибок: `send_error()` через `ErrorCallback`
  - Дедупликация и дата-чек: `process_news_item(title, content, link, raw_date, source)`
    - Собирает текст → `DeduplicationManager.is_duplicate` → `DateChecker.check_news_date` → `MessageSender.send_news_message` → `mark_as_posted`
  - Утилита задержки: `sleep_with_jitter(base_timeout, jitter)` — дополнительная рассинхронизация запросов

---

## 7) Парсеры: как именно работают

- `parsers/telegram_parser.py`
  - Создает `TelegramClient` (сессия из `Settings.telegram_session_name`)
  - Подписывается на события `events.NewMessage(chats=...)` для URLs каналов из `ChannelConfig`
  - При сообщении извлекает первые строки как заголовок, выясняет ссылку на пост, применяет `process_news_item`

- `parsers/rss_parser.py`
  - Для каждого RSS-источника запускает асинхронную задачу мониторинга
  - По таймеру (см. `Settings.request_timeout`) делает запрос `httpx`, парсит `feedparser`, по каждой записи вызывает `process_news_item`
  - Ошибки Connect/Read/HTTPStatus отправляет в канал через `ErrorCallback`

- `parsers/html_parsers/base_html.py`
  - Общая база: `fetch_url()` (HTTP с заголовками, обработка ошибок), `clean_html`, `extract_titles_from_html`, `extract_links_from_html`
  - Абстрактный `parse_news_items(http_client)` — конкретные HTML-парсеры обязаны реализовать

- `parsers/html_parsers/bcs_parser.py`
  - Сначала пробует RSS (`_parse_rss_feeds`), затем fallback на главную (`_parse_homepage`)
  - При отсутствии новостей делает паузу минимум 60 секунд перед следующим циклом
  - Каждый элемент прогоняет через `process_news_item`

---

## 8) Тонкая настройка и тюнинг

- «Только сегодняшние» новости: по умолчанию включено за счет `DateChecker.check_news_date(strict_today=True)`
- Окно «свежести»: `Settings.date_check_window_hours` (например, 12 часов)
- Дедупликация:
  - Глубина очереди: `Settings.duplicate_check_messages`
  - Длина отпечатка: `Settings.duplicate_check_chars`
- HTTP-поведение:
  - Таймауты и ретраи: `Settings.http_*`, `HTTPClient`
  - Заголовки: `get_browser_headers(accept_xml=True|False)`
- Интервалы запросов:
  - Базовый интервал — `Settings.request_timeout`
  - `sleep_with_jitter()` разбавляет одинаковые интервалы
- Телеграм-клиент:
  - Уровень логирования Telethon — `Settings.telethon_log_level`
  - Сессии — `Settings.telegram_session_name`, `Settings.bot_session_name`

---

## 9) Добавление нового HTML-парсера (пример)

1) Создайте `parsers/html_parsers/my_site.py`:
```python
from .base_html import BaseHTMLParser
import httpx
from typing import List, Tuple, Optional

class MySiteParser(BaseHTMLParser):
    async def parse_news_items(self, http_client: httpx.AsyncClient) -> List[Tuple[str, str, Optional[str]]]:
        # 1) загрузить страницу через self.fetch_url()
        # 2) извлечь заголовки/ссылки/дату
        # 3) вернуть список (title, link, raw_date_str)
        return []
```
2) Добавьте источник в `config/channels.py` как `HTMLChannel(..., parser_class='MySiteParser')`
3) При необходимости задайте специфичные настройки в `config/parsers.py`

---

## 10) Docker (опционально)

```bash
docker build -t tg-auto-news .
docker run -d --name tg-auto-news tg-auto-news
```

---

## 11) Частые вопросы

- Почему не публикует новость с датой в URL?
  - Если дата в URL не сегодняшняя — `DateChecker` её отсеет (поддерживаются `YYYY/MM/DD` и `DD/MM/YYYY`).
- Почему «Не найдено новостей в BCS» повторяется часто?
  - Теперь при отсутствии новостей парсер делает паузу минимум 60 сек перед повтором.
- Дубликаты всё равно проскочили — что делать?
  - Увеличьте `duplicate_check_chars`/`duplicate_check_messages` и проверьте, что текст формируется одинаково (источник/ссылка + текст).

---

## 12) Лицензия

MIT. 




<br/><br/>
---


