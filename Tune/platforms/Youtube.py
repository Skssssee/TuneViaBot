# Authored By Certified Coders © 2025
# FINAL FIX: ALWAYS SEND REAL YOUTUBE URL TO API

import asyncio
import contextlib
import json
import os
import re
import time
import aiohttp
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython import VideosSearch, Playlist

from Tune.utils.cookie_handler import COOKIE_PATH
from Tune.utils.database import is_on_off
from Tune.utils.downloader import yt_dlp_download
from Tune.utils.errors import capture_internal_err
from Tune.utils.formatters import time_to_seconds
from Tune.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL

# =========================
# CONFIG
# =========================
AUDIO_API = "http://152.42.187.207:8000/audio"

# =========================
# CACHES
# =========================
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()

# =========================
# HELPERS
# =========================
def _cookiefile_path() -> Optional[str]:
    try:
        if COOKIE_PATH and os.path.exists(COOKIE_PATH) and os.path.getsize(COOKIE_PATH) > 0:
            return str(COOKIE_PATH)
    except Exception:
        pass
    return None


def _cookies_args() -> List[str]:
    p = _cookiefile_path()
    return ["--cookies", p] if p else []


async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return b"", b"timeout"


@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    key = f"q:{query}"
    now = time.time()

    async with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return val
            _cache.pop(key, None)

    try:
        data = await VideosSearch(query, limit=1).next()
        result = data.get("result", [])
    except Exception:
        result = []

    if result:
        async with _cache_lock:
            _cache[key] = (now, result)

    return result


# =========================
# MAIN CLASS
# =========================
class YouTubeAPI:
    def __init__(self) -> None:
        self.base = "https://www.youtube.com/watch?v="
        self._url_re = re.compile(r"(youtube\.com|youtu\.be)")

    # ---------------------
    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid:
            return self.base + videoid

        link = link.strip()

        if "youtu.be/" in link:
            return self.base + link.split("/")[-1].split("?")[0]

        if "youtube.com" in link:
            return link.split("&")[0]

        return link

    # =====================
    # NEVER BLOCK BOT FLOW
    # =====================
    @capture_internal_err
    async def exists(self, link: str, videoid=None) -> bool:
        return True

    # =====================
    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message]
        if message.reply_to_message:
            msgs.append(message.reply_to_message)

        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for e in entities:
                if e.type == MessageEntityType.URL:
                    return text[e.offset:e.offset + e.length]
                if e.type == MessageEntityType.TEXT_LINK:
                    return e.url
        return None

    # =====================
    # TRACK (ALWAYS RETURNS REAL URL)
    # =====================
    @capture_internal_err
    async def track(self, link: str, videoid=None) -> Tuple[Dict, str]:
        prepared = self._prepare_link(link, videoid)

        info = None
        if prepared.startswith("http"):
            try:
                data = await VideosSearch(prepared, limit=1).next()
                info = data.get("result", [None])[0]
            except Exception:
                info = None
        else:
            res = await cached_youtube_search(prepared)
            info = res[0] if res else None

        if not info:
            raise ValueError("No YouTube results found")

        vidid = info.get("id")
        real_url = self.base + vidid

        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0]

        details = {
            "title": info.get("title", ""),
            "link": real_url,              # 🔥 REAL URL ONLY
            "vidid": vidid,
            "duration_min": info.get("duration") or "0:00",
            "thumb": thumb,
        }

        return details, vidid

    # =====================
    @capture_internal_err
    async def details(self, link: str, videoid=None):
        details, vidid = await self.track(link, videoid)
        sec = int(time_to_seconds(details["duration_min"]))
        return (
            details["title"],
            details["duration_min"],
            sec,
            details["thumb"],
            vidid,
        )

    async def title(self, link: str, videoid=None):
        return (await self.track(link, videoid))[0]["title"]

    async def duration(self, link: str, videoid=None):
        return (await self.track(link, videoid))[0]["duration_min"]

    async def thumbnail(self, link: str, videoid=None):
        return (await self.track(link, videoid))[0]["thumb"]

    # =====================
    # DOWNLOAD = API HIT (REAL URL)
    # =====================
    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
    ):
        # 🔥 ENSURE REAL YOUTUBE URL
        if not link.startswith("http"):
            link = self.base + link

        async with aiohttp.ClientSession() as session:
            async with session.get(
                AUDIO_API,
                params={"url": link},
                timeout=30
            ) as r:
                if r.status != 200:
                    print("API FAIL:", r.status, link)
                    return None, None

                data = await r.json()
                if data.get("status") != "success":
                    print("API ERROR:", data)
                    return None, None

                return data["audio"], True

    # =====================
    async def video(self, link: str, videoid=None):
        return await self.download(link, None)

    async def playlist(self, link, limit, user_id, videoid=None):
        try:
            plist = await Playlist.get(link)
            return [v["id"] for v in plist.get("videos", [])[:limit]]
        except Exception:
            return []

    async def formats(self, link: str, videoid=None):
        return [], link

    async def slider(self, link: str, query_type: int, videoid=None):
        d, vid = await self.track(link, videoid)
        return d["title"], d["duration_min"], d["thumb"], vid
