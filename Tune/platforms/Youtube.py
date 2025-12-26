# ===============================
# TuneViaBot - Youtube Platform
# Stable • Fail-safe • Production
# ===============================

import os
import re
import yt_dlp
import aiohttp
from typing import Union, Tuple

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


# ===============================
# Helpers
# ===============================

def _video_id(url: str) -> str:
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url.strip()


async def _download_from_api(video_id: str) -> str | None:
    """
    Download REAL audio from external API
    """
    out = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                YT_API,
                params={"url": video_id},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:

                if r.status != 200:
                    return None

                # ❌ JSON response = not audio
                if "application/json" in r.headers.get("content-type", ""):
                    return None

                with open(out, "wb") as f:
                    async for chunk in r.content.iter_chunked(1024 * 64):
                        f.write(chunk)

        if os.path.exists(out) and os.path.getsize(out) > 50_000:
            return out

        return None

    except Exception:
        return None


def _fallback_yt_dlp(url: str) -> str | None:
    """
    Local yt-dlp fallback (last resort)
    """
    vid = _video_id(url)
    out = os.path.join(DOWNLOAD_DIR, f"{vid}.mp3")

    opts = {
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
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        if os.path.exists(out) and os.path.getsize(out) > 50_000:
            return out

        return None

    except Exception:
        return None


# ===============================
# YouTube API (Main)
# ===============================

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(youtube\.com|youtu\.be)"

    # -------------------------
    async def exists(self, link: str, videoid=None) -> bool:
        return bool(re.search(self.regex, link))

    # -------------------------
    async def url(self, message: Message):
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
        """
        NEVER FAILS – even if search breaks
        """
        try:
            link = self.base + link if videoid else link
            res = VideosSearch(link, limit=1)
            data = (await res.next()).get("result")

            if not data:
                raise ValueError

            data = data[0]
            title = data.get("title")
            dur = data.get("duration")
            thumb = data.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
            vid = data.get("id")

            if not title or not vid:
                raise ValueError

            dur_s = int(time_to_seconds(dur)) if dur else 0
            return title, dur, dur_s, thumb, vid

        except Exception:
            # 🔥 SAFE FALLBACK
            vid = _video_id(link)
            return "Unknown Title", None, 0, "", vid

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
    async def video(self, *args, **kwargs):
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

        # 1️⃣ External API
        path = await _download_from_api(vid)
        if path:
            return path, True

        # 2️⃣ yt-dlp fallback
        path = _fallback_yt_dlp(link)
        if path:
            return path, True

        return None, False
