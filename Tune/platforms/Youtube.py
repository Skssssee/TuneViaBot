
import re
import aiohttp
import hashlib
from typing import Union, Tuple, Dict
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

AUDIO_API = "http://152.42.187.207:8000/audio"
YT_REGEX = r"(youtube\.com|youtu\.be)"

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(YT_REGEX)

    # -------------------------
    async def exists(self, link: str, videoid=None):
        if videoid:
            link = self.base + videoid
        return bool(self.regex.search(link))

    # -------------------------
    async def url(self, message: Message):
        msgs = [message]
        if message.reply_to_message:
            msgs.append(message.reply_to_message)

        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for e in entities:
                if e.type == MessageEntityType.URL:
                    return text[e.offset:e.offset + e.length]
                if e.type == MessageEntityType.TEXT_LINK:
                    return e.url
        return None

    # =====================
    # TRACK (NO FAIL EVER)
    # =====================
    async def track(
        self, link: str, videoid=None
    ) -> Tuple[Dict, str]:

        # -------- TEXT QUERY --------
        if not self.regex.search(link):
            fake_id = hashlib.md5(link.encode()).hexdigest()[:11]

            details = {
                "title": link[:60],
                "link": link,
                "vidid": fake_id,
                "duration_min": "0:00",
                "thumb": "https://i.imgur.com/8hY5K5R.jpg",
            }
            return details, fake_id

        # -------- YOUTUBE URL --------
        if videoid:
            link = self.base + videoid

        vidid = link.split("v=")[-1].split("&")[0]

        details = {
            "title": "YouTube Audio",
            "link": link,
            "vidid": vidid,
            "duration_min": "0:00",
            "thumb": f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg",
        }

        return details, vidid

    # =====================
    async def details(self, link: str, videoid=None):
        if not self.regex.search(link):
            fake_id = hashlib.md5(link.encode()).hexdigest()[:11]
            return (
                link[:60],
                "0:00",
                0,
                "https://i.imgur.com/8hY5K5R.jpg",
                fake_id,
            )

        if videoid:
            link = self.base + videoid

        vidid = link.split("v=")[-1].split("&")[0]
        return (
            "YouTube Audio",
            "0:00",
            0,
            f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg",
            vidid,
        )

    # =====================
    async def title(self, link: str, videoid=None):
        return link if not self.regex.search(link) else "YouTube Audio"

    async def duration(self, link: str, videoid=None):
        return "0:00"

    async def thumbnail(self, link: str, videoid=None):
        if not self.regex.search(link):
            return "https://i.imgur.com/8hY5K5R.jpg"
        vidid = link.split("v=")[-1].split("&")[0]
        return f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"

    # =====================
    # STREAM (VC)
    # =====================
    async def stream(self, link: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                AUDIO_API,
                params={"url": link},
                timeout=20
            ) as resp:

                if resp.status != 200:
                    return 0, "API error"

                data = await resp.json()
                if data.get("status") != "success":
                    return 0, data.get("error", "Failed")

                return 1, data["audio"]

    # =====================
    async def video(self, link: str, videoid=None):
        return await self.stream(link)

    async def playlist(self, link, limit, user_id, videoid=None):
        return []

    async def formats(self, link: str, videoid=None):
        return [], link

    async def slider(self, link: str, query_type: int, videoid=None):
        fake_id = hashlib.md5(link.encode()).hexdigest()[:11]
        return (
            link[:60],
            "0:00",
            "https://i.imgur.com/8hY5K5R.jpg",
            fake_id,
    )
