
import os
import re
import aiohttp
from typing import Union
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
from py_yt import VideosSearch
from Tune.utils.formatters import time_to_seconds   # ⚠️ TuneViaBot path

# ─────────────────────────────
# CONFIG
# ─────────────────────────────

MY_API_URL = "https://disabled-rosalinde-uhhy5-523ef0f0.koyeb.app"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ─────────────────────────────
# INTERNAL API DOWNLOAD
# ─────────────────────────────

async def _download_from_api(video_id: str, mode: str):
    ext = "mp3" if mode == "audio" else "mp4"
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 50 * 1024:
        return file_path

    url = f"{MY_API_URL}/{mode}?url=https://www.youtube.com/watch?v={video_id}"

    headers = {
        "User-Agent": UA,
        "Range": "bytes=0-"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=120) as resp:
                ct = resp.headers.get("Content-Type", "").lower()

                if resp.status != 200:
                    return None

                if mode == "audio" and "audio" not in ct:
                    return None
                if mode == "download" and "video" not in ct:
                    return None

                with open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(16384):
                        f.write(chunk)

        if os.path.exists(file_path) and os.path.getsize(file_path) > 50 * 1024:
            return file_path

        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

    return None

# ─────────────────────────────
# HELPERS
# ─────────────────────────────

def extract_video_id(link: str):
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    if "youtu.be/" in link:
        return link.split("youtu.be/")[-1].split("?")[0]
    return None

async def download_song(link: str):
    vid = extract_video_id(link)
    if not vid:
        return None
    return await _download_from_api(vid, "audio")

async def download_video(link: str):
    vid = extract_video_id(link)
    if not vid:
        return None
    return await _download_from_api(vid, "download")

# ─────────────────────────────
# YOUTUBE API CLASS
# ─────────────────────────────

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(youtube\.com|youtu\.be)"

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message):
        msgs = [message]
        if message.reply_to_message:
            msgs.append(message.reply_to_message)

        for msg in msgs:
            if msg.entities:
                for ent in msg.entities:
                    if ent.type == MessageEntityType.URL:
                        text = msg.text or msg.caption
                        return text[ent.offset: ent.offset + ent.length]

            if msg.caption_entities:
                for ent in msg.caption_entities:
                    if ent.type == MessageEntityType.TEXT_LINK:
                        return ent.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        r = VideosSearch(link, limit=1)
        data = (await r.next())["result"][0]

        title = data["title"]
        duration_min = data["duration"]
        duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        thumbnail = data["thumbnails"][0]["url"].split("?")[0]
        vidid = data["id"]

        return title, duration_min, duration_sec, thumbnail, vidid

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        r = VideosSearch(link, limit=1)
        data = (await r.next())["result"][0]

        track_details = {
            "title": data["title"],
            "link": data["link"],
            "vidid": data["id"],
            "duration_min": data["duration"],
            "thumb": data["thumbnails"][0]["url"].split("?")[0],
        }

        return track_details, data["id"]

    async def download(
        self,
        link: str,
        mystic=None,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        **kwargs,
    ):
        if videoid:
            link = self.base + link

        try:
            if video:
                path = await download_video(link)
            else:
                path = await download_song(link)

            if path:
                return path, True

        except Exception:
            pass

        return None, False
