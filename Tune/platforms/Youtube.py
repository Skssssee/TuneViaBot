
# ===============================
# TuneViaBot - Youtube Platform
# Fixed & Compatible
# ===============================

import os
import re
import json
import asyncio
from typing import Union, Tuple

import aiohttp
import yt_dlp

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from Tune.utils.formatters import time_to_seconds
from Tune.utils.errors import capture_internal_err

try:
    from youtubesearchpython.__future__ import VideosSearch
except ImportError:
    from youtubesearchpython import VideosSearch


# ===== CONFIG =====
YT_API = "http://152.42.187.207:8000/audio"
DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ===== HELPERS =====
def _video_id(url: str) -> str:
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url.strip()


async def _download_from_api(video_id: str) -> str | None:
    """
    Fetch audio stream URL from API and save real audio file
    """
    out_file = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                YT_API,
                params={"url": video_id},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:

                if r.status != 200:
                    return None

                ct = r.headers.get("content-type", "")
                if "application/json" in ct:
                    # ❌ JSON = NOT AUDIO
                    return None

                with open(out_file, "wb") as f:
                    async for chunk in r.content.iter_chunked(1024 * 64):
                        f.write(chunk)

        if os.path.exists(out_file) and os.path.getsize(out_file) > 50_000:
            return out_file

        return None

    except Exception:
        return None


def _fallback_yt_dlp(url: str) -> str | None:
    """
    Local yt-dlp fallback
    """
    vid = _video_id(url)
    out = os.path.join(DOWNLOAD_DIR, f"{vid}.mp3")

    ydl_opts = {
        "format": "bestaudio",
        "outtmpl": out,
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(out) and os.path.getsize(out) > 50_000:
            return out

        return None

    except Exception:
        return None


# ===============================
# YouTube API Class
# ===============================
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(youtube\.com|youtu\.be)"

    # -------------------------
    async def exists(self, link: str, videoid=None) -> bool:
        return bool(re.search(self.regex, link))

    # -------------------------
    async def url(self, message: Message) -> str | None:
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

    # -------------------------
    async def details(self, link: str, videoid=None):
        link = self.base + link if videoid else link
        res = VideosSearch(link, limit=1)
        data = (await res.next())["result"][0]

        title = data["title"]
        dur = data.get("duration")
        dur_s = int(time_to_seconds(dur)) if dur else 0
        thumb = data["thumbnails"][0]["url"].split("?")[0]
        vid = data["id"]

        return title, dur, dur_s, thumb, vid

    # -------------------------
    async def track(self, link: str, videoid=None):
        title, dur, _, thumb, vid = await self.details(link, videoid)

        return {
            "title": title,
            "link": self.base + vid,
            "vidid": vid,
            "duration_min": dur,
            "thumb": thumb,
        }, vid

    # -------------------------
    async def video(self, link: str, videoid=None):
        return 0, "Video not supported"

    # -------------------------
    async def playlist(self, *args, **kwargs):
        return []

    # -------------------------
    async def download(
        self,
        link: str,
        mystic=None,
        video: bool = False,
        videoid=None,
        **kwargs,
    ) -> Tuple[str | None, bool]:

        link = self.base + link if videoid else link
        vid = _video_id(link)

        # 1️⃣ Try external API
        path = await _download_from_api(vid)
        if path:
            return path, True

        # 2️⃣ Fallback yt-dlp
        path = _fallback_yt_dlp(link)
        if path:
            return path, True

        return None, False
