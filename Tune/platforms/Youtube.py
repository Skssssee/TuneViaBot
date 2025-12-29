# Authored By Certified Coders © 2025
# YouTube Platform – FINAL (yt-dlp search based)

import asyncio
import contextlib
import json
import os
import re
from typing import Dict, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from Tune.utils.cookie_handler import COOKIE_PATH
from Tune.utils.database import is_on_off
from Tune.utils.downloader import yt_dlp_download
from Tune.utils.errors import capture_internal_err
from Tune.utils.formatters import time_to_seconds
from Tune.utils.tuning import YTDLP_TIMEOUT


# =========================
# HELPERS
# =========================
def _cookiefile_path() -> Optional[str]:
    try:
        if COOKIE_PATH and os.path.exists(COOKIE_PATH) and os.path.getsize(COOKIE_PATH) > 0:
            return str(COOKIE_PATH)
    except Exception:
        pass
    return None


def _cookies_args():
    p = _cookiefile_path()
    return ["--cookies", p] if p else []


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

        return link  # text query remains text

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
    # TRACK (yt-dlp SEARCH)
    # =====================
    @capture_internal_err
    async def track(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[Dict, str]:

        prepared = self._prepare_link(link, videoid)

        # ========= TEXT QUERY =========
        if not prepared.startswith("http"):
            stdout, stderr = await _exec_proc(
                "yt-dlp",
                *(_cookies_args()),
                "--dump-json",
                f"ytsearch1:{prepared}"
            )

            if not stdout:
                raise ValueError(f"No YouTube results found for '{prepared}'")

            info = json.loads(stdout.decode())

        # ========= URL =========
        else:
            stdout, stderr = await _exec_proc(
                "yt-dlp",
                *(_cookies_args()),
                "--dump-json",
                prepared
            )

            if not stdout:
                raise ValueError(stderr.decode() if stderr else "yt-dlp failed")

            info = json.loads(stdout.decode())

        thumb = (
            info.get("thumbnail")
            or info.get("thumbnails", [{}])[-1].get("url", "")
        ).split("?")[0]

        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", self.base + info.get("id", "")),
            "vidid": info.get("id", ""),
            "duration_min": time_to_seconds(info.get("duration")),
            "thumb": thumb,
        }

        return details, info.get("id", "")

    # =====================
    # STREAM / DOWNLOAD
    # =====================
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
    ):
        prepared = self._prepare_link(link, videoid)

        # VIDEO STREAM
        if video:
            stdout, _ = await _exec_proc(
                "yt-dlp",
                *(_cookies_args()),
                "-g",
                "-f",
                "best[height<=720]",
                prepared,
            )
            return (stdout.decode().split("\n")[0], None) if stdout else (None, None)

        # AUDIO DOWNLOAD / STREAM
        p = await yt_dlp_download(prepared, type="audio", title=prepared)
        return (p, True) if p else (None, None)
