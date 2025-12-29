# Authored By Certified Coders © 2025
# YouTube Platform – FAST + COOKIE SAFE

import asyncio
import contextlib
import os
import re
import time
from typing import Dict, Optional, Tuple, Union

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from Tune.utils.errors import capture_internal_err
from Tune.utils.tuning import YTDLP_TIMEOUT


# =========================
# COOKIE PATH (FIXED)
# =========================
COOKIE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),  # Tune/
    "cookies",
    "cookies.txt",
)


# =========================
# STREAM CACHE
# =========================
_STREAM_CACHE: Dict[str, Tuple[str, float]] = {}
_CACHE_TTL = 300  # 5 minutes


# =========================
# PROCESS RUNNER
# =========================
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


# =========================
# MAIN CLASS
# =========================
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self._url_re = re.compile(r"(youtube\.com|youtu\.be)")

    # ---------------------
    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid:
            return self.base + videoid

        link = link.strip()

        if "youtu.be/" in link:
            return self.base + link.split("/")[-1].split("?")[0]

        if "youtube.com" in link:
            return link.split("&")[0]

        return link

    # ---------------------
    async def exists(self, link: str, videoid=None) -> bool:
        return bool(self._url_re.search(self._prepare_link(link, videoid)))

    # ---------------------
    async def url(self, message: Message) -> Optional[str]:
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

    # =====================
    # FAST TRACK (COOKIE SAFE)
    # =====================
    @capture_internal_err
    async def track(
        self,
        link: str,
        videoid: Union[str, bool, None] = None,
    ):

        prepared = self._prepare_link(link, videoid)
        now = time.time()

        # CACHE HIT
        if prepared in _STREAM_CACHE:
            url, ts = _STREAM_CACHE[prepared]
            if now - ts < _CACHE_TTL:
                return {
                    "title": prepared,
                    "link": url,
                    "vidid": None,
                    "duration_min": None,
                    "thumb": "",
                }, None

        # yt-dlp command (ANTI-BOT SAFE)
        cmd = [
            "yt-dlp",
            "--cookies", COOKIE_FILE,
            "--user-agent", "Mozilla/5.0 (Linux; Android 13; Pixel 7)",
            "--extractor-args", "youtube:player_client=android",
            "-f", "bestaudio",
            "-g",
            f"ytsearch1:{prepared}" if not prepared.startswith("http") else prepared,
        ]

        stdout, stderr = await _exec_proc(*cmd)

        if not stdout:
            raise ValueError(
                stderr.decode().strip() if stderr else "Failed to fetch stream"
            )

        stream_url = stdout.decode().strip().split("\n")[0]

        _STREAM_CACHE[prepared] = (stream_url, now)

        return {
            "title": prepared,
            "link": stream_url,
            "vidid": None,
            "duration_min": None,
            "thumb": "",
        }, None
