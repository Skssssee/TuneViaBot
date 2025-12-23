# Authored By Certified Coders © 2025
# Optimized Hybrid YouTube Engine (API + yt-dlp)

import asyncio
import contextlib
import json
import os
import re
import time
from typing import Dict, List, Optional, Tuple, Union

import aiohttp
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from Tune.utils.cookie_handler import COOKIE_PATH
from Tune.utils.database import is_on_off
from Tune.utils.downloader import yt_dlp_download
from Tune.utils.errors import capture_internal_err
from Tune.utils.formatters import time_to_seconds
from Tune.utils.tuning import YTDLP_TIMEOUT, YOUTUBE_META_MAX, YOUTUBE_META_TTL

# ──────────────────────────────────
# ENV
# ──────────────────────────────────
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"

# ──────────────────────────────────
# CACHE
# ──────────────────────────────────
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()

_formats_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_formats_lock = asyncio.Lock()

YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# ──────────────────────────────────
# HELPERS
# ──────────────────────────────────
def _cookiefile_path() -> Optional[str]:
    try:
        if COOKIE_PATH and os.path.exists(COOKIE_PATH) and os.path.getsize(COOKIE_PATH) > 0:
            return str(COOKIE_PATH)
    except Exception:
        pass
    return None


def _cookies_args() -> List[str]:
    path = _cookiefile_path()
    return ["--cookies", path] if path else []


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


# ──────────────────────────────────
# YOUTUBE API SEARCH (FAST)
# ──────────────────────────────────
async def youtube_api_search(query: str) -> Optional[Dict]:
    if not YOUTUBE_API_KEY:
        return None

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 1,
        "key": YOUTUBE_API_KEY,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(YT_SEARCH_URL, params=params) as r:
            if r.status != 200:
                return None
            data = await r.json()

    items = data.get("items")
    if not items:
        return None

    vid = items[0]["id"]["videoId"]
    snip = items[0]["snippet"]

    params = {
        "part": "contentDetails",
        "id": vid,
        "key": YOUTUBE_API_KEY,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(YT_VIDEO_URL, params=params) as r:
            info = await r.json()

    duration = info["items"][0]["contentDetails"]["duration"]

    return {
        "id": vid,
        "title": snip["title"],
        "duration": duration,
        "thumbnail": snip["thumbnails"]["high"]["url"],
    }


# ──────────────────────────────────
# CACHED SEARCH (API → fallback)
# ──────────────────────────────────
@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    key = f"q:{query}"
    now = time.time()

    async with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return val

    # 1️⃣ FAST API SEARCH
    api_res = await youtube_api_search(query)
    if api_res:
        result = [{
            "id": api_res["id"],
            "title": api_res["title"],
            "duration": api_res["duration"],
            "thumbnail": api_res["thumbnail"],
        }]
        async with _cache_lock:
            _cache[key] = (now, result)
        return result

    # 2️⃣ yt-dlp fallback
    stdout, _ = await _exec_proc(
        "yt-dlp", *(_cookies_args()), "--dump-json", "--no-warnings", f"ytsearch1:{query}"
    )
    if stdout:
        info = json.loads(stdout.decode())
        return [{
            "id": info.get("id"),
            "title": info.get("title"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
        }]

    return []


# ──────────────────────────────────
# MAIN CLASS
# ──────────────────────────────────
class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")

    def _prepare_link(self, link: str, videoid=None) -> str:
        if isinstance(videoid, str) and videoid:
            return self.base_url + videoid
        if link.startswith("http"):
            return link.split("&")[0]
        return link

    @capture_internal_err
    async def exists(self, link: str, videoid=None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset: ent.offset + ent.length]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url
        return None

    # ───────── Metadata ─────────
    @capture_internal_err
    async def details(self, query: str):
        data = await cached_youtube_search(query)
        if not data:
            raise ValueError("Video not found")

        v = data[0]
        return (
            v["title"],
            v["duration"],
            int(time_to_seconds(v["duration"])),
            v["thumbnail"],
            v["id"],
        )

    @capture_internal_err
    async def title(self, query: str) -> str:
        d = await cached_youtube_search(query)
        return d[0]["title"] if d else ""

    # ───────── Streaming ─────────
    @capture_internal_err
    async def video(self, link: str):
        stdout, stderr = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-g",
            "-f",
            "best[height<=?720]",
            link,
        )
        return (1, stdout.decode().strip()) if stdout else (0, stderr.decode())

    @capture_internal_err
    async def download(self, link: str, mystic, *, video=False):
        link = self._prepare_link(link)

        if video:
            if await is_on_off(1):
                p = await yt_dlp_download(link, type="video", title=await self.title(link))
                return (p, True) if p else (None, None)

        p = await yt_dlp_download(link, type="audio", title=await self.title(link))
        return (p, True) if p else (None, None)
