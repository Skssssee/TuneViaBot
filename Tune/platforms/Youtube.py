
import aiohttp
import asyncio
import re
from typing import Union
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

# =========================
# CONFIG
# =========================

AUDIO_API = "http://152.42.187.207:8000/audio"

YT_REGEX = r"(youtube\.com|youtu\.be)"

# =========================
# CORE
# =========================

class YouTubeAPI:
    def __init__(self):
        self.regex = re.compile(YT_REGEX)

    # -------------------------
    # CHECK LINK
    # -------------------------
    async def exists(self, link: str) -> bool:
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
                if ent.type in (MessageEntityType.URL, MessageEntityType.TEXT_LINK):
                    return ent.url if ent.url else text[ent.offset:ent.offset + ent.length]
        return None

    # -------------------------
    # GET AUDIO STREAM
    # -------------------------
    async def audio(self, link: str):
        params = {"url": link}

        async with aiohttp.ClientSession() as session:
            async with session.get(AUDIO_API, params=params, timeout=20) as resp:
                if resp.status != 200:
                    return 0, f"API HTTP {resp.status}"

                data = await resp.json()

                if data.get("status") != "success":
                    return 0, data.get("error", "API failed")

                return 1, data["audio"]

    # -------------------------
    # VC STREAM ENTRY
    # -------------------------
    async def stream(self, link: str):
        ok, result = await self.audio(link)
        if not ok:
            return 0, result

        # result is DIRECT GOOGLEVIDEO URL
        return 1, result
