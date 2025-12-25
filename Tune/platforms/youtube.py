import re
import aiohttp
from typing import Union

from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

# ================= CONFIG =================
MY_API_URL = "http://127.0.0.1:8000"   # tumhara yt-api
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
    async def track(self, link: str, videoid: Union[bool, str] = None):
        """
        NO SEARCH. NO FAILURE.
        Always returns valid track for any YouTube link.
        """

        if videoid:
            link = self.base + link

        original = link

        # remove params (?si= etc)
        if "?" in link:
            link = link.split("?")[0]

        # extract video id
        vid = None
        if "v=" in link:
            vid = link.split("v=")[-1]
        elif "youtu.be/" in link:
            vid = link.split("youtu.be/")[-1]

        if not vid:
            # fallback (should not crash Tune)
            return {
                "title": "YouTube Audio",
                "link": original,
                "vidid": original,
                "duration_min": "0:00",
                "thumb": "",
            }, original

        return {
            "title": "YouTube Audio",
            "link": self.base + vid,
            "vidid": vid,
            "duration_min": "0:00",
            "thumb": "",
        }, vid

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
        Returns direct googlevideo stream URL
        (NO file download, NO storage usage)
        """

        if videoid:
            link = self.base + link

        if "?" in link:
            link = link.split("?")[0]

        vid = None
        if "v=" in link:
            vid = link.split("v=")[-1]
        elif "youtu.be/" in link:
            vid = link.split("youtu.be/")[-1]

        if not vid:
            return None, False

        try:
            async with aiohttp.ClientSession() as session:

                # -------- AUDIO --------
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
