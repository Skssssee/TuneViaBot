
# ===============================
# TuneViaBot - Youtube Platform
# STREAM BASED (NO FILE DOWNLOAD)
# ===============================

import re
import aiohttp
from typing import Union, Tuple

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from Tune.utils.formatters import time_to_seconds

try:
    from youtubesearchpython.__future__ import VideosSearch
except ImportError:
    from youtubesearchpython import VideosSearch


# 🔥 YOUR AUDIO API (returns JSON: { "audio": "<direct_url>" })
YT_API = "http://152.42.187.207:8000/audio"


# ===============================
# HELPERS
# ===============================
def extract_video_id(url: str) -> str:
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url.strip()


# ===============================
# YOUTUBE API CLASS
# ===============================
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(youtube\.com|youtu\.be)"

    # -------------------------
    async def exists(self, link: str, videoid=None) -> bool:
        return bool(re.search(self.regex, link))

    # -------------------------
    async def url(self, message: Message) -> Union[str, None]:
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

    # ===============================
    # 🔥 MAIN STREAM FUNCTION
    # ===============================
    async def download(
        self,
        link: str,
        mystic=None,
        video: bool = False,
        videoid=None,
        **kwargs,
    ) -> Tuple[str | None, bool]:

        link = self.base + link if videoid else link
        vid = extract_video_id(link)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    YT_API,
                    params={"url": vid},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:

                    if r.status != 200:
                        return None, False

                    data = await r.json()
                    audio_url = data.get("audio")

                    if not audio_url:
                        return None, False

                    # ✅ VERY IMPORTANT
                    # direct=True => StreamController knows this is HTTP stream
                    return audio_url, True

        except Exception:
            return None, False
