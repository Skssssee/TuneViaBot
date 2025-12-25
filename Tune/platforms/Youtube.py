import re
from typing import Union

from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

try:
    from py_yt import VideosSearch
except ImportError:
    from youtubesearchpython.__future__ import VideosSearch

from Tune.utils.formatters import time_to_seconds

# ================= CONFIG =================
MY_API_URL = "http://127.0.0.1:8000"   # apna yt-api URL yahan
# ========================================


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"

    # -------------------------------------------------
    # BASIC CHECK
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    # -------------------------------------------------
    # URL EXTRACT FROM MESSAGE
    async def url(self, message: Message) -> Union[str, None]:
        messages = [message]
        if message.reply_to_message:
            messages.append(message.reply_to_message)

        for msg in messages:
            if msg.entities:
                for ent in msg.entities:
                    if ent.type == MessageEntityType.URL:
                        text = msg.text or msg.caption
                        return text[ent.offset : ent.offset + ent.length]

            if msg.caption_entities:
                for ent in msg.caption_entities:
                    if ent.type == MessageEntityType.TEXT_LINK:
                        return ent.url
        return None

    # -------------------------------------------------
    # VIDEO DETAILS
    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        search = VideosSearch(link, limit=1)
        result = (await search.next())["result"][0]

        title = result["title"]
        duration_min = result["duration"]
        duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        thumb = result["thumbnails"][0]["url"].split("?")[0]
        vidid = result["id"]

        return title, duration_min, duration_sec, thumb, vidid

    # -------------------------------------------------
    # TRACK (Tune expects this)
    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        search = VideosSearch(link, limit=1)
        result = (await search.next())["result"][0]

        track_details = {
            "title": result["title"],
            "link": result["link"],
            "vidid": result["id"],
            "duration_min": result["duration"],
            "thumb": result["thumbnails"][0]["url"].split("?")[0],
        }

        return track_details, result["id"]

    # -------------------------------------------------
    # DOWNLOAD (CRITICAL FOR Tune STREAM ENGINE)
    async def download(
        self,
        link: str,
        mystic=None,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ):
        """
        Tune expects:
        return (path_or_url, direct_bool)

        direct=True  => stream URL
        direct=False => local file (we DON'T use this)
        """

        if videoid:
            link = self.base + link

        vid = link.split("v=")[-1].split("&")[0] if "v=" in link else link

        # ---------- AUDIO (default) ----------
        if not video:
            stream_url = (
                f"{MY_API_URL}/audio?"
                f"url=https://www.youtube.com/watch?v={vid}"
            )
            return stream_url, True

        # ---------- VIDEO ----------
        stream_url = (
            f"{MY_API_URL}/video?"
            f"url=https://www.youtube.com/watch?v={vid}"
        )
        return stream_url, True
