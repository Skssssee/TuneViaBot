# Authored By Certified Coders © 2025
# Clean API-Based YouTube Handler
# NO yt-dlp | NO proxy | NO cookies here
# Uses external API only

import os
import re
import aiohttp
import asyncio
from typing import Union, Tuple, Dict, List
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from Tune.utils.formatters import time_to_seconds
from Tune import LOGGER

try:
    from py_yt import VideosSearch
except ImportError:
    from youtubesearchpython.__future__ import VideosSearch


# ================= CONFIG =================

API_BASE = "http://152.42.187.207:8000"
DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

YT_REGEX = r"(youtube\.com|youtu\.be)"
YT_BASE = "https://www.youtube.com/watch?v="

log = LOGGER("YouTubeAPI")

# ==========================================


def extract_video_id(link: str) -> str:
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    return link.split("/")[-1].split("?")[0]


# ================= API DOWNLOADERS =================

async def download_song(link: str) -> Union[str, None]:
    try:
        vid = extract_video_id(link)
        if not vid:
            return None

        file_path = f"{DOWNLOAD_DIR}/{vid}.mp3"
        if os.path.exists(file_path):
            return file_path

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/audio",
                params={"url": vid},
                timeout=300
            ) as resp:

                if resp.status != 200:
                    return None

                with open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 32):
                        f.write(chunk)

        return file_path if os.path.exists(file_path) else None

    except Exception as e:
        log.error(f"AUDIO ERROR: {e}")
        return None


async def download_video(link: str) -> Union[str, None]:
    try:
        vid = extract_video_id(link)
        if not vid:
            return None

        file_path = f"{DOWNLOAD_DIR}/{vid}.mp4"
        if os.path.exists(file_path):
            return file_path

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/video",
                params={"url": vid},
                timeout=600
            ) as resp:

                if resp.status != 200:
                    return None

                with open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 64):
                        f.write(chunk)

        return file_path if os.path.exists(file_path) else None

    except Exception as e:
        log.error(f"VIDEO ERROR: {e}")
        return None


# ================= MAIN CLASS =================

class YouTubeAPI:
    def __init__(self):
        self.base = YT_BASE
        self.regex = re.compile(YT_REGEX)

    async def exists(self, link: str, videoid: Union[str, bool] = None) -> bool:
        return bool(self.regex.search(link))

    async def url(self, message: Message):
        msgs = [message]
        if message.reply_to_message:
            msgs.append(message.reply_to_message)

        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset: ent.offset + ent.length]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url
        return None

    async def details(self, link: str, videoid: Union[str, bool] = None):
        vid = extract_video_id(link)
        search = VideosSearch(vid, limit=1)
        data = (await search.next())["result"][0]

        duration = data.get("duration")
        seconds = int(time_to_seconds(duration)) if duration else 0

        return (
            data["title"],
            duration,
            seconds,
            data["thumbnails"][0]["url"].split("?")[0],
            data["id"],
        )

    async def title(self, link: str, videoid=None):
        vid = extract_video_id(link)
        search = VideosSearch(vid, limit=1)
        return (await search.next())["result"][0]["title"]

    async def duration(self, link: str, videoid=None):
        vid = extract_video_id(link)
        search = VideosSearch(vid, limit=1)
        return (await search.next())["result"][0].get("duration")

    async def thumbnail(self, link: str, videoid=None):
        vid = extract_video_id(link)
        search = VideosSearch(vid, limit=1)
        return (await search.next())["result"][0]["thumbnails"][0]["url"].split("?")[0]

    async def track(self, link: str, videoid=None):
        vid = extract_video_id(link)
        search = VideosSearch(vid, limit=1)
        r = (await search.next())["result"][0]

        track = {
            "title": r["title"],
            "link": r["link"],
            "vidid": r["id"],
            "duration_min": r.get("duration"),
            "thumb": r["thumbnails"][0]["url"].split("?")[0],
        }
        return track, r["id"]

    async def video(self, link: str, videoid=None):
        file = await download_video(link)
        if file:
            return 1, file
        return 0, "Video failed"

    async def playlist(self, link, limit, user_id, videoid=None):
        return []

    async def formats(self, link, videoid=None):
        return [], link

    async def slider(self, link, query_type, videoid=None):
        search = VideosSearch(link, limit=10)
        r = (await search.next())["result"][query_type]
        return (
            r["title"],
            r.get("duration"),
            r["thumbnails"][0]["url"].split("?")[0],
            r["id"],
        )

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid=None,
        **kwargs,
    ):
        if video:
            file = await download_video(link)
        else:
            file = await download_song(link)

        if file:
            return file, True
        return None, False
