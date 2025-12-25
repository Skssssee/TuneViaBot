import asyncio
import re
from typing import Union, Dict, List

import aiohttp
import psutil
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

try:
    from py_yt import VideosSearch
except ImportError:
    from youtubesearchpython.__future__ import VideosSearch

from Tune.utils.formatters import time_to_seconds

# ================= CONFIG =================
MY_API_URL = "http://127.0.0.1:8000"  # apna API URL yahan
CPU_DOWNGRADE_AT = 80
CPU_UPGRADE_AT = 30
CHECK_INTERVAL = 15

AUDIO_QUALITIES = [256, 192, 128]   # kbps (high -> low)

# ================= GLOBAL STATE =================
GROUP_QUEUE: Dict[int, List[str]] = {}
GROUP_PLAYING: Dict[int, bool] = {}

# ================= STREAM HELPERS =================
async def get_audio_stream(link: str, quality: int):
    vid = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    url = f"{MY_API_URL}/audio?url=https://youtube.com/watch?v={vid}&quality={quality}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                data = await r.json()
                return data.get("audio_url")
    return None

# ================= PLAYER CORE =================
async def play_audio_dynamic(player, group_id: int, link: str):
    # quality select at song start
    idx = 0 if psutil.cpu_percent() < CPU_UPGRADE_AT else len(AUDIO_QUALITIES) - 1

    while True:
        q = AUDIO_QUALITIES[idx]
        try:
            stream_url = await get_audio_stream(link, q)
            if not stream_url:
                raise RuntimeError("no stream url")
            await player.play(stream_url)
        except Exception:
            if idx < len(AUDIO_QUALITIES) - 1:
                idx += 1
                continue
            return

        # monitor during playback (downgrade only)
        while player.is_playing():
            await asyncio.sleep(CHECK_INTERVAL)
            if psutil.cpu_percent() > CPU_DOWNGRADE_AT and idx < len(AUDIO_QUALITIES) - 1:
                idx += 1
                await player.stop()
                break

# ================= QUEUE ENGINE =================
def add_to_queue(group_id: int, link: str):
    GROUP_QUEUE.setdefault(group_id, []).append(link)

async def process_queue(player, group_id: int):
    if GROUP_PLAYING.get(group_id):
        return
    GROUP_PLAYING[group_id] = True
    try:
        while GROUP_QUEUE.get(group_id):
            link = GROUP_QUEUE[group_id].pop(0)
            await play_audio_dynamic(player, group_id, link)
    finally:
        GROUP_PLAYING[group_id] = False

# ================= YOUTUBE API =================
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Union[str, None]:
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
        s = VideosSearch(link, limit=1)
        r = (await s.next())["result"][0]
        title = r["title"]
        duration_min = r["duration"]
        thumb = r["thumbnails"][0]["url"].split("?")[0]
        vidid = r["id"]
        duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumb, vidid

    # ===== THIS WAS MISSING =====
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

    async def play(self, player, group_id: int, link: str):
        add_to_queue(group_id, link)
        if not GROUP_PLAYING.get(group_id):
            asyncio.create_task(process_queue(player, group_id))
