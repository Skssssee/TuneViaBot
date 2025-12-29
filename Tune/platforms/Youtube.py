import aiohttp
import hashlib
from typing import Dict, Tuple, Union
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

# =========================
# CONFIG
# =========================
AUDIO_API = "http://152.42.187.207:8000/audio"

# =========================
# MAIN CLASS
# =========================
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="

    # ---------------------
    # MUST ALWAYS TRUE
    # ---------------------
    async def exists(self, link: str, videoid=None) -> bool:
        return True

    # ---------------------
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
    # TRACK (🔥 NEVER FAIL)
    # =====================
    async def track(
        self, link: str, videoid: Union[str, bool, None] = None
    ) -> Tuple[Dict, str]:

        if link.startswith("http"):
            if videoid:
                link = self.base + videoid
            vidid = link.split("v=")[-1].split("&")[0]
        else:
            # text query → fake safe id
            vidid = hashlib.md5(link.encode()).hexdigest()[:11]

        details = {
            "title": link[:60],
            "link": link,
            "vidid": vidid,
            "duration_min": "0:00",   # 🔥 SAFE
            "thumb": f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg",
        }

        return details, vidid

    # =====================
    async def details(self, link: str, videoid=None):
        if link.startswith("http"):
            if videoid:
                link = self.base + videoid
            vidid = link.split("v=")[-1].split("&")[0]
        else:
            vidid = hashlib.md5(link.encode()).hexdigest()[:11]

        return (
            link[:60],
            "0:00",
            0,
            f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg",
            vidid,
        )

    async def title(self, link: str, videoid=None):
        return link[:60]

    async def duration(self, link: str, videoid=None):
        return "0:00"

    async def thumbnail(self, link: str, videoid=None):
        vidid = hashlib.md5(link.encode()).hexdigest()[:11]
        return f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"

    # =====================
    # 🔥 DOWNLOAD = API HIT
    # =====================
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        **kwargs
    ):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                AUDIO_API,
                params={"url": link},
                timeout=30
            ) as resp:

                if resp.status != 200:
                    return None, None

                data = await resp.json()
                if data.get("status") != "success":
                    return None, None

                # ✅ DIRECT GOOGLEVIDEO URL
                return data["audio"], True

    # =====================
    async def video(self, link: str, videoid=None):
        return await self.download(link, None)

    async def playlist(self, link, limit, user_id, videoid=None):
        return []

    async def formats(self, link: str, videoid=None):
        return [], link

    async def slider(self, link: str, query_type: int, videoid=None):
        vidid = hashlib.md5(link.encode()).hexdigest()[:11]
        return (
            link[:60],
            "0:00",
            f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg",
            vidid,
                    )
