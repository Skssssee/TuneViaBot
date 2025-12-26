
import asyncio
import os
import re
from typing import Union

import aiohttp
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from Tune.utils.formatters import time_to_seconds
from Tune import LOGGER

try:
    from py_yt import VideosSearch
except ImportError:
    from youtubesearchpython.__future__ import VideosSearch


LOGGER = LOGGER("Tune.platforms.Youtube")

# ================= CONFIG =================

API_URLS = [
    "http://152.42.187.207:8000",  # YOUR API
]

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# =========================================


async def download_song(link: str) -> str:
    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    file_path = f"{DOWNLOAD_DIR}/{video_id}.mp3"

    # already valid
    if os.path.exists(file_path) and os.path.getsize(file_path) > 50_000:
        return file_path

    for api in API_URLS:
        try:
            async with aiohttp.ClientSession() as session:
                # STEP 1 — get stream url (JSON)
                async with session.get(
                    f"{api}/audio",
                    params={"url": link},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as r:
                    if r.status != 200:
                        continue

                    data = await r.json()
                    audio_url = data.get("audio_url")

                    if not audio_url:
                        continue

                # STEP 2 — download real audio bytes
                async with session.get(
                    audio_url,
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as audio:
                    if audio.status != 200:
                        continue

                    with open(file_path, "wb") as f:
                        async for chunk in audio.content.iter_chunked(64 * 1024):
                            f.write(chunk)

                # validate
                if os.path.exists(file_path) and os.path.getsize(file_path) > 50_000:
                    return file_path
                else:
                    os.remove(file_path)

        except Exception as e:
            LOGGER.error(f"Download failed: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)

    return None


# ================= YOUTUBE CLASS =================

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid=False):
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Union[str, None]:
        messages = [message]
        if message.reply_to_message:
            messages.append(message.reply_to_message)

        for msg in messages:
            if msg.entities:
                for e in msg.entities:
                    if e.type == MessageEntityType.URL:
                        return msg.text[e.offset : e.offset + e.length]
            if msg.caption_entities:
                for e in msg.caption_entities:
                    if e.type == MessageEntityType.TEXT_LINK:
                        return e.url
        return None

    async def details(self, link: str):
        results = VideosSearch(link, limit=1)
        data = (await results.next())["result"][0]
        return (
            data["title"],
            data["duration"],
            int(time_to_seconds(data["duration"])) if data["duration"] else 0,
            data["thumbnails"][0]["url"].split("?")[0],
            data["id"],
        )

    async def track(self, link: str):
        results = VideosSearch(link, limit=1)
        data = (await results.next())["result"][0]
        return {
            "title": data["title"],
            "link": data["link"],
            "vidid": data["id"],
            "duration_min": data["duration"],
            "thumb": data["thumbnails"][0]["url"].split("?")[0],
        }, data["id"]

    async def download(
        self,
        link: str,
        mystic=None,
        video: bool = False,
        videoid: bool = False,
    ):
        if videoid:
            link = self.base + link

        path = await download_song(link)
        if not path:
            return None, False

        return path, True
