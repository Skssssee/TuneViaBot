# Tune/platforms/Youtube.py

import asyncio
import os
import re
from typing import Union, Tuple

import aiohttp
import yt_dlp

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from Tune.utils.formatters import time_to_seconds
from Tune.utils.errors import AssistantErr
from Tune import LOGGER

try:
    from py_yt import VideosSearch
except ImportError:
    from youtubesearchpython.__future__ import VideosSearch


LOGGER = LOGGER(__name__)

BASE_URL = "https://www.youtube.com/watch?v="
YT_REGEX = re.compile(r"(youtube\.com|youtu\.be)")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# =========================
# INTERNAL HELPERS
# =========================

def clean_url(link: str) -> str:
    if "youtu.be/" in link:
        return BASE_URL + link.split("/")[-1].split("?")[0]
    if "watch?v=" in link:
        return link.split("&")[0]
    return link


async def yt_search(query: str):
    search = VideosSearch(query, limit=1)
    data = await search.next()
    if not data or not data.get("result"):
        return None
    return data["result"][0]


# =========================
# DOWNLOAD HELPERS
# =========================

async def yt_dlp_audio(link: str) -> str:
    vid = link.split("v=")[-1]
    out = f"{DOWNLOAD_DIR}/{vid}.mp3"

    if os.path.exists(out) and os.path.getsize(out) > 100_000:
        return out

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{DOWNLOAD_DIR}/{vid}.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    loop = asyncio.get_event_loop()

    def run():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([link])

    await loop.run_in_executor(None, run)

    if not os.path.exists(out) or os.path.getsize(out) < 100_000:
        raise AssistantErr("FAILED TO DOWNLOAD AUDIO")

    return out


# =========================
# MAIN CLASS
# =========================

class YouTubeAPI:
    def __init__(self):
        self.base = BASE_URL

    # -------------------------
    async def exists(self, link: str, videoid: Union[str, bool] = None):
        if videoid:
            link = self.base + videoid
        return bool(YT_REGEX.search(link))

    # -------------------------
    async def url(self, message: Message):
        msgs = [message]
        if message.reply_to_message:
            msgs.append(message.reply_to_message)

        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset : ent.offset + ent.length]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url
        return None

    # -------------------------
    async def details(
        self, link: str, videoid: Union[str, bool] = None
    ) -> Tuple[str, str, int, str, str]:

        if videoid:
            link = self.base + videoid

        link = clean_url(link)
        result = await yt_search(link)

        if not result:
            raise AssistantErr("FAILED TO FETCH TRACK DETAILS")

        title = result.get("title")
        duration = result.get("duration")
        thumb = result["thumbnails"][0]["url"].split("?")[0]
        vidid = result["id"]
        duration_sec = int(time_to_seconds(duration)) if duration else 0

        return title, duration, duration_sec, thumb, vidid

    # -------------------------
    async def track(self, link: str, videoid: Union[str, bool] = None):
        if videoid:
            link = self.base + videoid

        link = clean_url(link)
        result = await yt_search(link)

        if not result:
            raise AssistantErr("FAILED TO FETCH TRACK DETAILS")

        track = {
            "title": result["title"],
            "link": result["link"],
            "vidid": result["id"],
            "duration_min": result.get("duration"),
            "thumb": result["thumbnails"][0]["url"].split("?")[0],
        }

        return track, result["id"]

    # -------------------------
    async def download(
        self,
        link: str,
        mystic=None,
        video: Union[bool, str] = None,
        videoid: Union[str, bool] = None,
        **kwargs,
    ):

        if videoid:
            link = self.base + videoid

        link = clean_url(link)

        try:
            path = await yt_dlp_audio(link)
            return path, True
        except Exception as e:
            LOGGER.error(f"Download failed: {e}")
            return None, False
