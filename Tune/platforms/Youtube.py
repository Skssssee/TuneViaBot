# Authored By Certified Coders © 2025
# Fixed & Optimized by ChatGPT

import re
import json
import asyncio
import contextlib
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from youtubesearchpython import VideosSearch
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

from Tune.utils.formatters import time_to_seconds
from Tune.utils.errors import capture_internal_err


YOUTUBE_REGEX = re.compile(r"(youtube\.com|youtu\.be)")
BASE_URL = "https://www.youtube.com/watch?v="


class YouTubeAPI:
    def __init__(self):
        pass

    # --------------------------------------------------
    # URL PARSER
    # --------------------------------------------------
    def _clean_url(self, link: str) -> str:
        if "youtu.be/" in link:
            return BASE_URL + link.split("/")[-1].split("?")[0]
        if "watch?v=" in link:
            return link.split("&")[0]
        if "shorts/" in link or "live/" in link:
            return BASE_URL + link.split("/")[-1].split("?")[0]
        return link

    # --------------------------------------------------
    # CHECK YOUTUBE LINK
    # --------------------------------------------------
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        if videoid:
            link = BASE_URL + videoid
        return bool(YOUTUBE_REGEX.search(link))

    # --------------------------------------------------
    # GET URL FROM MESSAGE
    # --------------------------------------------------
    async def url(self, message: Message) -> Optional[str]:
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

    # --------------------------------------------------
    # SEARCH VIDEO (FAST)
    # --------------------------------------------------
    def _search(self, query: str) -> Optional[Dict]:
        search = VideosSearch(query, limit=1)
        data = search.result()
        if not data or not data.get("result"):
            return None
        return data["result"][0]

    # --------------------------------------------------
    # DETAILS (USED BY STREAM.PY)
    # --------------------------------------------------
    async def details(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[str, Optional[str], int, str, str]:

        if videoid:
            link = BASE_URL + videoid

        link = self._clean_url(link)
        info = self._search(link)

        if not info:
            raise Exception("No video found")

        title = info["title"]
        duration = info.get("duration")
        duration_sec = int(time_to_seconds(duration)) if duration else 0
        thumb = info["thumbnails"][0]["url"].split("?")[0]
        vidid = info["id"]

        return title, duration, duration_sec, thumb, vidid

    # --------------------------------------------------
    # TRACK (USED BY /play)
    # --------------------------------------------------
    async def track(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[Dict, str]:

        if videoid:
            link = BASE_URL + videoid

        link = self._clean_url(link)
        info = self._search(link)

        if not info:
            raise Exception("Track not found")

        track = {
            "title": info["title"],
            "link": info["link"],
            "vidid": info["id"],
            "duration_min": info.get("duration"),
            "thumb": info["thumbnails"][0]["url"].split("?")[0],
        }

        return track, info["id"]

    # --------------------------------------------------
    # STREAM URL (NO DOWNLOAD)
    # --------------------------------------------------
    async def download(
        self,
        link: str,
        mystic=None,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        **kwargs,
    ) -> Tuple[str, bool]:

        if videoid:
            link = BASE_URL + videoid

        link = self._clean_url(link)

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
        }

        loop = asyncio.get_event_loop()

        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                return info.get("url")

        stream_url = await loop.run_in_executor(None, _extract)

        if not stream_url:
            raise Exception("Audio stream not found")

        # True = direct stream (no file)
        return stream_url, True

    # --------------------------------------------------
    # LIVE VIDEO SUPPORT
    # --------------------------------------------------
    async def video(self, link: str):
        link = self._clean_url(link)

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "best",
        }

        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                return info.get("url")

        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(None, _extract)

        if not url:
            return 0, None

        return 1, url
