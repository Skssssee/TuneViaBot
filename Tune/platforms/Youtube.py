# Authored By Certified Coders © 2025
# YouTube Platform – FINAL STABLE (API BASED | NO yt-dlp | NO cookies)

import time
import re
import urllib.parse
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


# =========================
# SAFE API FETCHER
# =========================
async def _safe_api_fetch(api: str, link: str) -> dict:
    encoded_url = urllib.parse.quote(link, safe="")

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13)",
        "Accept": "application/json",
        "Connection": "keep-alive",
    }

    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.get(api, params={"url": encoded_url}) as resp:
            text = await resp.text()

            if resp.status != 200:
                raise ValueError(f"API HTTP {resp.status}: {text[:200]}")

            try:
                data = await resp.json()
            except Exception:
                raise ValueError(f"Invalid JSON response: {text[:200]}")

    if not isinstance(data, dict):
        raise ValueError(f"Unexpected API response: {data}")

    if data.get("status") != "success":
        raise ValueError(f"API error response: {data}")

    return data


# =========================
# MAIN CLASS
# =========================
class YouTubeAPI:
    def __init__(self):
        self._url_re = re.compile(r"(youtube\.com|youtu\.be)")

    # ---------------------
    # URL EXISTS CHECK
    # ---------------------
    async def exists(self, link: str, videoid=None) -> bool:
        return bool(self._url_re.search(link or ""))

    # ---------------------
    # EXTRACT URL FROM MESSAGE
    # ---------------------
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
        now = time.time()
        cache_key = f"audio:{link}"

        # CACHE HIT
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

        # FETCH FROM API
        data = await _safe_api_fetch(AUDIO_API, link)

        stream_url = data.get("audio")
        if not stream_url:
            raise ValueError("Audio URL missing in API response")

        _STREAM_CACHE[cache_key] = (stream_url, now)

        return {
            "title": link,
            "link": stream_url,
            "vidid": None,
            "duration_min": None,
            "thumb": "",
        }, None

    # =====================
    # VIDEO TRACK
    # =====================
    @capture_internal_err
    async def video(self, link: str, videoid=None):
        now = time.time()
        cache_key = f"video:{link}"

        # CACHE HIT
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

        # FETCH FROM API
        data = await _safe_api_fetch(VIDEO_API, link)

        stream_url = data.get("video")
        if not stream_url:
            raise ValueError("Video URL missing in API response")

        _STREAM_CACHE[cache_key] = (stream_url, now)

        return {
            "title": link,
            "link": stream_url,
            "vidid": None,
            "duration_min": None,
            "thumb": "",
        }, None
