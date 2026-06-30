"""Адаптер Telegram: пост в канал бренда через Bot API.

Самый надёжный канал: Bot API — обычные HTTPS-запросы, без антибота и браузера.
Картинка прикрепляется всегда (sendPhoto с подписью). Если текст длиннее лимита
подписи Telegram (1024 символа) — отправляем фото с короткой подписью, а полный
текст следом отдельным сообщением.

Нужно два значения (env / GitHub Secrets):
  TELEGRAM_BOT_TOKEN  — токен бота от @BotFather (вида 123456:ABC-...)
  TELEGRAM_CHANNEL    — канал: @username или числовой chat_id (-100...).
Бот должен быть АДМИНОМ канала с правом публикации.
"""

import os
import html as _html
import requests

from .. import config

CAPTION_LIMIT = 1024


class TelegramClient:
    def __init__(self, token=None, channel=None):
        self.token = token or config.TELEGRAM_BOT_TOKEN
        self.channel = str(channel or config.TELEGRAM_CHANNEL or "")

    def _check(self):
        if not self.token or not self.channel:
            raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHANNEL не заданы (см. .env / Secrets).")

    def _api(self, method: str, data: dict, files=None) -> dict:
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        r = requests.post(url, data=data, files=files, timeout=60)
        payload = r.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error в {method}: {payload}")
        return payload["result"]

    @staticmethod
    def _links_html(links: dict) -> str:
        """Ссылки на маркеты вшиты в слова (HTML-якоря), без сырых URL."""
        if not links:
            return ""
        parts = []
        if links.get("wb"):
            parts.append(f'<a href="{_html.escape(links["wb"], quote=True)}">Wildberries</a>')
        if links.get("ozon"):
            parts.append(f'<a href="{_html.escape(links["ozon"], quote=True)}">Ozon</a>')
        return ("\n\n🛒 Заказать: " + " · ".join(parts)) if parts else ""

    @staticmethod
    def _caption_html(title: str, text: str, links: dict) -> str:
        """Заголовок жирным, тело обычным, ссылки вшиты в слова."""
        return (f"<b>{_html.escape(title.strip())}</b>\n\n"
                f"{_html.escape(text.strip())}"
                f"{TelegramClient._links_html(links)}")

    @staticmethod
    def _visible_len(title: str, text: str, links: dict) -> int:
        """Длина видимого текста (без HTML-тегов) для проверки лимита подписи."""
        base = len(title.strip()) + 2 + len(text.strip())
        if links and (links.get("wb") or links.get("ozon")):
            base += len("\n\n🛒 Заказать: ") + len("Wildberries · Ozon")
        return base

    def _post_url(self, msg: dict) -> str:
        ch = self.channel.lstrip("@")
        mid = msg.get("message_id") if isinstance(msg, dict) else None
        if ch and not ch.lstrip("-").isdigit() and mid:
            return f"https://t.me/{ch}/{mid}"
        return f"https://t.me/{ch}" if ch else ""

    def publish(self, title: str, text: str, image_path: str = None, links: dict = None) -> dict:
        self._check()
        caption = self._caption_html(title, text, links)
        if image_path and os.path.exists(image_path):
            if self._visible_len(title, text, links) <= CAPTION_LIMIT:
                with open(image_path, "rb") as f:
                    res = self._api("sendPhoto",
                                    {"chat_id": self.channel, "caption": caption, "parse_mode": "HTML"},
                                    files={"photo": ("image.jpg", f, "image/jpeg")})
                return {"raw": res, "url": self._post_url(res)}
            # длинный текст: фото с жирным заголовком-подписью + полный текст следом
            with open(image_path, "rb") as f:
                res = self._api("sendPhoto",
                                {"chat_id": self.channel,
                                 "caption": f"<b>{_html.escape(title.strip())}</b>",
                                 "parse_mode": "HTML"},
                                files={"photo": ("image.jpg", f, "image/jpeg")})
            self._api("sendMessage",
                      {"chat_id": self.channel,
                       "text": _html.escape(text.strip()) + self._links_html(links),
                       "parse_mode": "HTML", "disable_web_page_preview": True})
            return {"raw": res, "url": self._post_url(res)}
        res = self._api("sendMessage",
                        {"chat_id": self.channel, "text": caption,
                         "parse_mode": "HTML", "disable_web_page_preview": True})
        return {"raw": res, "url": self._post_url(res)}
