
# Authored By Certified Coders © 2025
# FAST + FIXED VERSION (4GB VPS OPTIMIZED)

import asyncio
import contextlib
import json
import os
import re
import time
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch, Playlist

from Tune.utils.cookie_handler import COOKIE_PATH
from Tune.utils.database import is_on_off
from Tune.utils.downloader import yt_dlp_download
from Tune.utils.errors import capture_internal_err
from Tune.utils.formatters import time_to_seconds
from Tune.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL


# ======================
# GLOBAL CACHES
# ======================
_search_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()


# ======================
# CONSTANTS
# ======================
YT_WATCH = "https://www.youtube.com/watch?v="


# ======================
# HELPERS
# ======================
def _cookiefile() -> Optional[str]:
    try:
        if COOKIE_PATH and os.path.exists(COOKIE_PATH) and os.path.getsize(COOKIE_PATH) > 0:
            return str(COOKIE_PATH)
    except Exception:
        pass
    return None


async def _run_yt_dlp_json(url: str) -> Optional[Dict]:
    """Last-resort yt-dlp (slow)"""
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--dump-json",
        "--no-warnings",
        *(
            ["--cookies", _cookiefile()]
            if _cookiefile()
            else []
        ),
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
        return json.loads(out.decode()) if out else None
    except Exception:
        with contextlib.suppress(Exception):
            proc.kill()
        return None


# ======================
# FAST SEARCH CACHE
# ======================
@capture_internal_err
async def cached_search(query: str) -> List[Dict]:
    now = time.time()
    key = query.lower()

    async with _cache_lock:
        if key in _search_cache:
            ts, data = _search_cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return data

    try:
        data = await VideosSearch(query, limit=1).next()
        res = data.get("result", [])
    except Exception:
        res = []

    if res:
        async with _cache_lock:
            if len(_search_cache) > YOUTUBE_META_MAX:
                _search_cache.clear()
            _search_cache[key] = (now, res)

    return res


# ======================
# MAIN API
# ======================
class YouTubeAPI:
    def __init__(self) -> None:
        self._yt_rx = re.compile(r"(youtube\.com|youtu\.be)")

    # ------------------
    # NORMALIZE URL
    # ------------------
    def _normalize(self, link: str, videoid: Union[str, None] = None) -> str:
        if videoid:
            return YT_WATCH + videoid.strip()

        link = link.strip()
        if "youtu.be/" in link:
            link = YT_WATCH + link.split("/")[-1]
        elif "/shorts/" in link or "/live/" in link:
            link = YT_WATCH + link.split("/")[-1]

        return link.split("&")[0]

    # ------------------
    # EXTRACT URL
    # ------------------
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            for ent in (msg.entities or []) + (msg.caption_entities or []):
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset: ent.offset + ent.length].split("&")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url.split("&")[0]
        return None

    # ------------------
    # 🔥 FAST TRACK (NO DOUBLE FETCH)
    # ------------------
    @capture_internal_err
    async def track(
        self,
        link: str,
        videoid: Union[str, None] = None
    ) -> Tuple[Dict, str]:

        link = self._normalize(link, videoid)

        # ⚡ FAST: VideosSearch only
        data = await cached_search(link)
        info = data[0] if data else None

        # ❌ yt-dlp ONLY if search failed
        if not info or not info.get("id"):
            info = await _run_yt_dlp_json(link)

        if not info:
            raise ValueError("No track info found")

        # ✅ DURATION FIX (seconds only)
        raw = info.get("duration", 0)
        if isinstance(raw, str):
            duration = int(time_to_seconds(raw))
        elif isinstance(raw, int):
            duration = raw
        else:
            duration = 0

        thumb = (
            info.get("thumbnail")
            or (info.get("thumbnails", [{}])[-1].get("url", ""))
        ).split("?")[0]

        details = {
            "title": info.get("title", "Unknown"),
            "link": info.get("webpage_url", link),
            "vidid": info.get("id", ""),
            "duration": duration,   # 🔥 seconds only
            "thumb": thumb,
        }

        return details, info.get("id", "")

    # ------------------
    # DOWNLOAD (FAST)
    # ------------------
    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic=None,
        *,
        video: bool = False,
        videoid: Union[str, None] = None
    ) -> Tuple[Optional[str], bool]:

        link = self._normalize(link, videoid)

        # ---------- VIDEO ----------
        if video:
            if await is_on_off(1):
                p = await yt_dlp_download(
                    link,
                    type="video",
                    title="video"
                )
                return (p, True) if p else (None, False)

            # ⚡ FAST STREAM (NO JSON)
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "-f", "best[height<=720]",
                "-g", link,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, _ = await proc.communicate()
            return (out.decode().strip(), False) if out else (None, False)

        # ---------- AUDIO ----------
        p = await yt_dlp_download(
            link,
            type="audio",
            title="audio"
        )
        return (p, True) if p else (None, False)
