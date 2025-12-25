# Authored By Certified Coders © 2025
# Fully Optimized + Track Fixed Version

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


# =========================
# GLOBAL CACHES
# =========================
_search_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_info_cache: Dict[str, Tuple[float, Dict]] = {}
_formats_cache: Dict[str, Tuple[float, List[Dict]]] = {}

_cache_lock = asyncio.Lock()


# =========================
# CONSTANTS
# =========================
YT_WATCH = "https://www.youtube.com/watch?v="
YT_PLAYLIST = "https://youtube.com/playlist?list="


# =========================
# HELPERS
# =========================
def _cookiefile() -> Optional[str]:
    try:
        if COOKIE_PATH and os.path.exists(COOKIE_PATH) and os.path.getsize(COOKIE_PATH) > 0:
            return str(COOKIE_PATH)
    except Exception:
        pass
    return None


def _yt_args() -> List[str]:
    return ["--cookies", _cookiefile()] if _cookiefile() else []


async def _run_yt_dlp(*args: str) -> Optional[Dict]:
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        *(_yt_args()),
        "--dump-json",
        "--no-warnings",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
        return json.loads(stdout.decode()) if stdout else None
    except Exception:
        with contextlib.suppress(Exception):
            proc.kill()
        return None


# =========================
# SEARCH CACHE
# =========================
@capture_internal_err
async def cached_search(query: str) -> List[Dict]:
    now = time.time()
    key = f"s:{query}"

    async with _cache_lock:
        if key in _search_cache and now - _search_cache[key][0] < YOUTUBE_META_TTL:
            return _search_cache[key][1]

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


# =========================
# MAIN API
# =========================
class YouTubeAPI:
    def __init__(self) -> None:
        self._url_rx = re.compile(r"(youtube\.com|youtu\.be)")

    # ---------------------
    # NORMALIZE URL
    # ---------------------
    def _normalize(self, link: str, videoid: Union[str, None] = None) -> str:
        if videoid:
            return YT_WATCH + videoid.strip()

        link = link.strip()
        if "youtu.be/" in link:
            link = YT_WATCH + link.split("/")[-1]
        elif "/shorts/" in link or "/live/" in link:
            link = YT_WATCH + link.split("/")[-1]

        return link.split("&")[0]

    # ---------------------
    # EXTRACT URL
    # ---------------------
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

    # ---------------------
    # INFO (CACHED)
    # ---------------------
    @capture_internal_err
    async def info(self, query: str) -> Optional[Dict]:
        query = self._normalize(query)
        now = time.time()

        async with _cache_lock:
            if query in _info_cache and now - _info_cache[query][0] < YOUTUBE_META_TTL:
                return _info_cache[query][1]

        if query.startswith("http"):
            info = await _run_yt_dlp(query)
        else:
            res = await cached_search(query)
            info = res[0] if res else None

        if info:
            async with _cache_lock:
                if len(_info_cache) > YOUTUBE_META_MAX:
                    _info_cache.clear()
                _info_cache[query] = (now, info)

        return info

    # ---------------------
    # BASIC META
    # ---------------------
    async def title(self, link: str) -> str:
        i = await self.info(link)
        return i.get("title", "") if i else ""

    async def duration(self, link: str) -> int:
        i = await self.info(link)
        d = i.get("duration", 0) if i else 0
        return int(time_to_seconds(d)) if isinstance(d, str) else int(d)

    async def thumbnail(self, link: str) -> str:
        i = await self.info(link)
        return (i.get("thumbnail") or "").split("?")[0] if i else ""

    async def is_live(self, link: str) -> bool:
        i = await self.info(link)
        return bool(i and i.get("is_live"))

    # ---------------------
    # ✅ TRACK (FIXED)
    # ---------------------
    @capture_internal_err
    async def track(
        self,
        link: str,
        videoid: Union[str, None] = None
    ) -> Tuple[Dict, str]:

        link = self._normalize(link, videoid)

        info = await self.info(link)

        if not info or not info.get("id"):
            info = await _run_yt_dlp(link)

        if not info:
            raise ValueError(f"No track info found for: {link}")

        thumb = (
            info.get("thumbnail")
            or (info.get("thumbnails", [{}])[-1].get("url"))
            or ""
        ).split("?")[0]

        duration = info.get("duration")
        if isinstance(duration, str):
            duration = int(time_to_seconds(duration))
        elif not isinstance(duration, int):
            duration = 0

        details = {
            "title": info.get("title", "Unknown"),
            "link": info.get("webpage_url", link),
            "vidid": info.get("id", ""),
            "duration_min": duration,
            "thumb": thumb,
        }

        return details, info.get("id", "")

    # ---------------------
    # FORMATS
    # ---------------------
    async def formats(self, link: str) -> List[Dict]:
        link = self._normalize(link)
        now = time.time()

        async with _cache_lock:
            if link in _formats_cache and now - _formats_cache[link][0] < YOUTUBE_META_TTL:
                return _formats_cache[link][1]

        out = []
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "cookiefile": _cookiefile()}) as ydl:
                info = ydl.extract_info(link, download=False)
                for f in info.get("formats", []):
                    if not f.get("filesize") or "dash" in str(f.get("format", "")).lower():
                        continue
                    out.append({
                        "format": f["format"],
                        "ext": f["ext"],
                        "filesize": f["filesize"],
                        "format_id": f["format_id"],
                        "note": f.get("format_note"),
                    })
        except Exception:
            pass

        async with _cache_lock:
            _formats_cache[link] = (now, out)

        return out

    # ---------------------
    # PLAYLIST
    # ---------------------
    async def playlist(self, link: str, limit: int) -> List[str]:
        try:
            plist = await Playlist.get(link)
            return [v["id"] for v in plist.get("videos", [])[:limit]]
        except Exception:
            info = await _run_yt_dlp("--flat-playlist", "--playlist-end", str(limit), link)
            return [e.get("id") for e in info.get("entries", [])] if info else []

    # ---------------------
    # DOWNLOAD
    # ---------------------
    async def download(
        self,
        link: str,
        *,
        video: bool = False
    ) -> Tuple[Optional[str], bool]:

        link = self._normalize(link)

        if video:
            if await self.is_live(link):
                return link, False

            if await is_on_off(1):
                p = await yt_dlp_download(link, type="video", title=await self.title(link))
                return p, True

            info = await _run_yt_dlp("-g", "-f", "best[height<=720]", link)
            return info, False

        p = await yt_dlp_download(link, type="audio", title=await self.title(link))
        return p, True
