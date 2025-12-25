import re
import aiohttp
from typing import Union

from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

try:
    from py_yt import VideosSearch
except ImportError:
    from youtubesearchpython.__future__ import VideosSearch

from Tune.utils.formatters import time_to_seconds

# ================= CONFIG =================
MY_API_URL = "http://127.0.0.1:8000"   # apna yt-api yahan
# ========================================


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"

    # -------------------------------------------------
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    # -------------------------------------------------
    async def url(self, message: Message) -> Union[str, None]:
        msgs = [message]
        if message.reply_to_message:
            msgs.append(message.reply_to_message)

        for msg in msgs:
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
    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        s = VideosSearch(link, limit=1)
        r = (await s.next())["result"][0]

        title = r["title"]
        duration_min = r["duration"]
        duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        thumb = r["thumbnails"][0]["url"].split("?")[0]
        vidid = r["id"]

        return title, duration_min, duration_sec, thumb, vidid

    # -------------------------------------------------
    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        s = VideosSearch(link, limit=1)
        r = (await s.next())["result"][0]

        track_details = {
            "title": r["title"],
            "link": r["link"],
            "vidid": r["id"],
            "duration_min": r["duration"],
            "thumb": r["thumbnails"][0]["url"].split("?")[0],
        }

        return track_details, r["id"]

    # -------------------------------------------------
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
        Tune stream engine compatibility
        Returns: (stream_url, direct=True)
        """

        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        vid = link.split("v=")[-1] if "v=" in link else link

        try:
            async with aiohttp.ClientSession() as session:

                # -------- AUDIO (default) --------
                if not video:
                    async with session.get(
                        f"{MY_API_URL}/audio?url=https://www.youtube.com/watch?v={vid}",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as r:
                        data = await r.json()
                        audio_url = data.get("audio_url")
                        if audio_url:
                            return audio_url, True
                        return None, False

                # -------- VIDEO (optional) --------
                async with session.get(
                    f"{MY_API_URL}/video?url=https://www.youtube.com/watch?v={vid}",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as r:
                    data = await r.json()
                    video_url = data.get("video_url")
                    if video_url:
                        return video_url, True
                    return None, False

        except Exception:
            return None, False
