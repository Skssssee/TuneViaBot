# Authored By Certified Coders © 2025
# YouTube Platform – API Based (AUDIO + VIDEO)

import time
import re
import aiohttp
from typing import Dict, Optional, Tuple, Union

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from Tune.utils.errors import capture_internal_err


# =========================
# API ENDPOINTS
# =========================
AUDIO_API = "http://152.42.187.207:8000/audio"
VIDEO_API = "http://152.42.187.207:8000/video"

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
    # AUDIO TRACK
    # =====================
    @capture_internal_err
    async def track(self, link: str, videoid=None):
        return await self._fetch(link, AUDIO_API)

    # =====================
    # VIDEO TRACK
    # =====================
    @capture_internal_err
    async def video(self, link: str, videoid=None):
        return await self._fetch(link, VIDEO_API)

    # =====================
    # CORE FETCHER
    # =====================
    async def _fetch(self, link: str, api: str):
        now = time.time()

        # CACHE
        cache_key = f"{api}:{link}"
        if cache_key in _STREAM_CACHE:
            url, ts = _STREAM_CACHE[cache_key]
            if now - ts < _CACHE_TTL:
                return {
                    "title": link,
                    "link": url,
                    "vidid": None,
                    "duration_min": None,
                    "thumb": "",
                }, None

        async with aiohttp.ClientSession() as session:
            async with session.get(api, params={"url": link}, timeout=20) as resp:
                if resp.status != 200:
                    raise ValueError(f"API failed with {resp.status}")

                data = await resp.json()

        if data.get("status") != "success":
            raise ValueError(f"API error response: {data}")

        stream_url = data.get("audio") or data.get("video")
        if not stream_url:
            raise ValueError(f"No stream URL in response: {data}")

        _STREAM_CACHE[cache_key] = (stream_url, now)

        return {
            "title": link,
            "link": stream_url,
            "vidid": None,
            "duration_min": None,
            "thumb": "",
        }, None
