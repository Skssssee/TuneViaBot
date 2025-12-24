# Authored By Certified Coders © 2025
# Fixed & Stabilized for TuneViaBot

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


# ================= CACHE =================
_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()


# ================= HELPERS =================
def _cookiefile_path() -> Optional[str]:
    try:
        path = str(COOKIE_PATH)
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return path
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


# ================= SEARCH CACHE =================
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

        if len(_cache) > YOUTUBE_META_MAX:
            _cache.clear()

    try:
        data = await VideosSearch(query, limit=1).next()
        result = data.get("result", [])
    except Exception:
        result = []

    if result:
        async with _cache_lock:
            _cache[key] = (now, result)

    return result


# ================= MAIN CLASS =================
class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")

    # ---------- URL NORMALIZER ----------
    def _prepare_link(self, link: str, videoid=None) -> str:
        if videoid:
            link = self.base_url + str(videoid)

        link = link.strip()

        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1]

        return link.split("&")[0]

    # ---------- EXISTS ----------
    async def exists(self, link: str, videoid=None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    # ---------- URL FROM MESSAGE ----------
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset : ent.offset + ent.length].split("&")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url.split("&")[0]
        return None

    # ---------- FETCH META ----------
    async def _fetch_video_info(self, query: str) -> Optional[Dict]:
        query = self._prepare_link(query)

        if not query.startswith("http"):
            res = await cached_youtube_search(query)
            return res[0] if res else None

        stdout, _ = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "--dump-json",
            "--no-warnings",
            query,
        )

        if stdout:
            return json.loads(stdout.decode())

        return None

    # ================= REQUIRED FUNCTIONS =================

    # ---------- TRACK (FIXED) ----------
    async def track(self, link: str, videoid=None):
        link = self._prepare_link(link, videoid)
        info = await self._fetch_video_info(link)

        if not info:
            raise Exception("Video not found")

        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        )

        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", link),
            "vidid": info.get("id", ""),
            "duration_min": info.get("duration"),
            "thumb": thumb.split("?")[0],
        }

        return details, info.get("id", "")

    # ---------- DETAILS ----------
    async def details(self, link: str, videoid=None):
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise Exception("No details found")

        duration = info.get("duration")
        seconds = int(time_to_seconds(duration)) if duration else 0

        return (
            info.get("title", ""),
            duration,
            seconds,
            info.get("thumbnail", ""),
            info.get("id", ""),
        )

    # ---------- VIDEO STREAM ----------
    async def video(self, link: str, videoid=None):
        link = self._prepare_link(link, videoid)
        stdout, stderr = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            link,
        )
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    # ---------- PLAYLIST ----------
    async def playlist(self, link: str, limit: int, user_id, videoid=None):
        if videoid:
            link = self.playlist_url + str(videoid)

        link = self._prepare_link(link)

        try:
            plist = await Playlist.get(link)
            return [
                v["id"]
                for v in plist.get("videos", [])[:limit]
                if v.get("id")
            ]
        except Exception:
            pass

        stdout, _ = await _exec_proc(
            "yt-dlp",
            *(_cookies_args()),
            "--get-id",
            "--flat-playlist",
            "--playlist-end",
            str(limit),
            link,
        )

        return stdout.decode().strip().split("\n") if stdout else []

    # ---------- DOWNLOAD (CRITICAL FIX) ----------
    async def download(
        self,
        link: str,
        mystic=None,
        *,
        video: Union[bool, str, None] = None,
        videoid=None,
    ):
        link = self._prepare_link(link, videoid)

        # VIDEO MODE
        if video:
            stdout, _ = await _exec_proc(
                "yt-dlp",
                *(_cookies_args()),
                "-g",
                "-f",
                "best[height<=?720][width<=?1280]",
                link,
            )
            if stdout:
                return stdout.decode().split("\n")[0], None
            return None, None

        # AUDIO MODE
        path = await yt_dlp_download(link, type="audio")
        return path, True
