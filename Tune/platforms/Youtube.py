# Authored By Certified Coders © 2025
# Optimized for FAST VC Streaming (NO DOWNLOAD)

import asyncio
import contextlib
import json
import os
import re
from typing import Optional, Tuple, Union

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython import VideosSearch

from Tune.utils.cookie_handler import COOKIE_PATH
from Tune.utils.errors import capture_internal_err
from Tune.utils.formatters import time_to_seconds


YTDLP_TIMEOUT = 12


# ===================== HELPERS =====================

def _cookiefile() -> Optional[str]:
    try:
        if COOKIE_PATH and os.path.exists(COOKIE_PATH) and os.path.getsize(COOKIE_PATH) > 0:
            return str(COOKIE_PATH)
    except Exception:
        pass
    return None


async def _exec(*args: str) -> Tuple[str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
        return out.decode().strip(), err.decode().strip()
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return "", "timeout"


# ===================== MAIN CLASS =====================

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(r"(youtube\.com|youtu\.be)")

    # ---------- URL EXTRACT (FIXES AttributeError url) ----------
    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        texts = [message]
        if message.reply_to_message:
            texts.append(message.reply_to_message)

        for msg in texts:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset: ent.offset + ent.length].split("&")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url.split("&")[0]
        return None

    # ---------- CHECK ----------
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        if videoid:
            link = self.base + str(videoid)
        return bool(self.regex.search(link))

    # ---------- SEARCH / DETAILS ----------
    @capture_internal_err
    async def details(self, query: str, videoid: Union[str, bool, None] = None):
        if videoid:
            query = self.base + str(videoid)

        query = query.split("&")[0]
        data = await VideosSearch(query, limit=1).next()

        if not data.get("result"):
            raise Exception("No results")

        r = data["result"][0]
        dur = r.get("duration")
        dur_sec = int(time_to_seconds(dur)) if dur else 0

        return (
            r["title"],
            dur,
            dur_sec,
            r["thumbnails"][0]["url"].split("?")[0],
            r["id"],
        )

    # ---------- TRACK ----------
    @capture_internal_err
    async def track(self, query: str, videoid: Union[str, bool, None] = None):
        if videoid:
            query = self.base + str(videoid)

        query = query.split("&")[0]
        data = await VideosSearch(query, limit=1).next()

        if not data.get("result"):
            raise Exception("Track not found")

        r = data["result"][0]
        return {
            "title": r["title"],
            "link": r["link"],
            "vidid": r["id"],
            "duration_min": r.get("duration"),
            "thumb": r["thumbnails"][0]["url"].split("?")[0],
        }, r["id"]

    # ---------- CORE STREAM (FAST & SAFE) ----------
    @capture_internal_err
    async def _stream_url(self, vidid: str) -> str:
        url = self.base + vidid
        cookies = _cookiefile()

        cmd = [
            "yt-dlp",
            "-g",
            "-f",
            "bestaudio",
            "--no-playlist",
            "--extractor-args",
            "youtube:player_client=android",
            url,
        ]

        if cookies:
            cmd.insert(1, "--cookies")
            cmd.insert(2, cookies)

        out, err = await _exec(*cmd)
        if not out:
            raise Exception(err or "yt-dlp failed")

        return out.split("\n")[0]

    # ---------- DOWNLOAD (STREAM ONLY) ----------
    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic=None,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        **_
    ):
        vidid = videoid or link.split("v=")[-1].split("&")[0]
        stream = await self._stream_url(vidid)

        # IMPORTANT:
        # True = direct stream (NO DOWNLOAD)
        return stream, True

    # ---------- LIVE ----------
    @capture_internal_err
    async def video(self, link: str):
        vidid = link.split("v=")[-1].split("&")[0]
        return 1, await self._stream_url(vidid)
