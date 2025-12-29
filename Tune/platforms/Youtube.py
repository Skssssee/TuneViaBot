
# Authored By Certified Coders © 2025
# YouTube Platform – API Based (NO yt-dlp | NO cookies)

import time
import re
import aiohttp
from typing import Dict, Optional, Tuple, Union

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from Tune.utils.errors import capture_internal_err


# =========================
# CONFIG
# =========================
AUDIO_API = "http://152.42.187.207:8000/audio"

# =========================
# CACHE
# =========================
_STREAM_CACHE: Dict[str, Tuple[str, float]] = {}
_CACHE_TTL = 300  # 5 minutes


class YouTubeAPI:
    def __init__(self):
        self._url_re = re.compile(r"(youtube\.com|youtu\.be)")

    async def exists(self, link: str, videoid=None) -> bool:
        return bool(self._url_re.search(link))

    async def url(self, message: Message) -> Optional[str]:
        msgs = [message]
        if message.reply_to_message:
            msgs.append(message.reply_to_message)

        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for e in entities:
                if e.type == MessageEntityType.URL:
                    return text[e.offset : e.offset + e.length]
                if e.type == MessageEntityType.TEXT_LINK:
                    return e.url
        return None

    # =====================
    # TRACK (API BASED)
    # =====================
    @capture_internal_err
    async def track(self, link: str, videoid=None):
        now = time.time()

        # CACHE
        if link in _STREAM_CACHE:
            url, ts = _STREAM_CACHE[link]
            if now - ts < _CACHE_TTL:
                return {
                    "title": link,
                    "link": url,
                    "vidid": None,
                    "duration_min": None,
                    "thumb": "",
                }, None

        # API CALL
        async with aiohttp.ClientSession() as session:
            async with session.get(AUDIO_API, params={"url": link}) as resp:
                if resp.status != 200:
                    raise ValueError(f"API failed with {resp.status}")

                data = await resp.json()

        # FLEXIBLE RESPONSE HANDLING
        stream_url = (
            data.get("audio")
            or data.get("url")
            or data.get("stream")
        )

        if not stream_url:
            raise ValueError(f"Invalid API response: {data}")

        # SAVE CACHE
        _STREAM_CACHE[link] = (stream_url, now)

        return {
            "title": link,
            "link": stream_url,
            "vidid": None,
            "duration_min": None,
            "thumb": "",
        }, None
