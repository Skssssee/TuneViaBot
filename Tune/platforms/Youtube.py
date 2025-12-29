import re
import aiohttp
from typing import Union, Tuple
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

# =========================
# CONFIG
# =========================

AUDIO_API = "http://152.42.187.207:8000/audio"
YT_REGEX = r"(youtube\.com|youtu\.be)"

# =========================
# YOUTUBE API CLASS
# =========================

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(YT_REGEX)

    # -------------------------
    # CHECK YOUTUBE LINK
    # -------------------------
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(self.regex.search(link))

    # -------------------------
    # EXTRACT URL FROM MESSAGE
    # -------------------------
    async def url(self, message: Message) -> Union[str, None]:
        messages = [message]
        if message.reply_to_message:
            messages.append(message.reply_to_message)

        for msg in messages:
            text = msg.text or msg.caption
            entities = msg.entities or msg.caption_entities or []
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset: ent.offset + ent.length]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url
        return None

    # -------------------------
    # BASIC DETAILS (BOT NEEDS)
    # -------------------------
    async def details(
        self,
        link: str,
        videoid: Union[bool, str] = None
    ) -> Tuple[str, str, int, str, str]:

        if videoid:
            link = self.base + link

        vidid = link.split("v=")[-1].split("&")[0]

        title = "YouTube Audio"
        duration_min = "Unknown"
        duration_sec = 0
        thumb = f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"

        return title, duration_min, duration_sec, thumb, vidid

    # -------------------------
    # TRACK (MOST IMPORTANT)
    # -------------------------
    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link

        vidid = link.split("v=")[-1].split("&")[0]

        track_details = {
            "title": "YouTube Audio",
            "link": link,
            "vidid": vidid,
            "duration_min": "Unknown",
            "thumb": f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg",
        }

        return track_details, vidid

    # -------------------------
    # TITLE ONLY
    # -------------------------
    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return "YouTube Audio"

    # -------------------------
    # DURATION ONLY
    # -------------------------
    async def duration(self, link: str, videoid: Union[bool, str] = None):
        return "Unknown"

    # -------------------------
    # THUMBNAIL ONLY
    # -------------------------
    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        vidid = link.split("v=")[-1].split("&")[0]
        return f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"

    # -------------------------
    # STREAM AUDIO (VC)
    # -------------------------
    async def stream(self, link: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                AUDIO_API,
                params={"url": link},
                timeout=20
            ) as resp:

                if resp.status != 200:
                    return 0, f"API HTTP {resp.status}"

                data = await resp.json()

                if data.get("status") != "success":
                    return 0, data.get("error", "Failed to fetch audio")

                # direct googlevideo URL
                return 1, data["audio"]

    # -------------------------
    # VIDEO (BOT EXPECTS METHOD)
    # -------------------------
    async def video(self, link: str, videoid: Union[bool, str] = None):
        # audio-only bot, so reuse stream
        return await self.stream(link)

    # -------------------------
    # PLAYLIST (SAFE EMPTY)
    # -------------------------
    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        return []

    # -------------------------
    # FORMATS (NOT USED)
    # -------------------------
    async def formats(self, link: str, videoid: Union[bool, str] = None):
        return [], link

    # -------------------------
    # SLIDER (SEARCH FALLBACK)
    # -------------------------
    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        vidid = link.split("v=")[-1].split("&")[0]
        thumb = f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"
        return "YouTube Audio", "Unknown", thumb, vidid
