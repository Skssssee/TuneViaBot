import asyncio
import time
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

MY_API_URL = "http://152.42.187.207:8000"

AUDIO_QUALITIES = [256, 192, 128]
VIDEO_QUALITIES = [720, 480, 360]

CPU_DOWNGRADE_AT = 80
CPU_UPGRADE_AT = 30
CHECK_INTERVAL = 15

# ================= GLOBAL STATE =================

GROUP_QUEUE: Dict[int, List[str]] = {}        # group_id -> [youtube links]
GROUP_PLAYING: Dict[int, bool] = {}           # group_id -> playing or not

# ================= STREAM HELPERS =================

async def get_audio_stream(link: str, quality: int):
    vid = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    api = f"{MY_API_URL}/audio?url=https://youtube.com/watch?v={vid}&quality={quality}"
    async with aiohttp.ClientSession() as s:
        async with s.get(api, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                return (await r.json()).get("audio_url")
    return None

# ================= PLAYER CORE =================

async def play_audio_dynamic(player, group_id: int, link: str):
    # upgrade only at song start
    idx = 0 if psutil.cpu_percent() < CPU_UPGRADE_AT else len(AUDIO_QUALITIES) - 1

    while True:
        q = AUDIO_QUALITIES[idx]
        try:
            url = await get_audio_stream(link, q)
            await player.play(url)
        except Exception:
            if idx < len(AUDIO_QUALITIES) - 1:
                idx += 1
                continue
            return

        # monitor current song (downgrade only)
        while player.is_playing():
            await asyncio.sleep(CHECK_INTERVAL)
            if psutil.cpu_percent() > CPU_DOWNGRADE_AT:
                if idx < len(AUDIO_QUALITIES) - 1:
                    idx += 1
                    await player.stop()
                    break
                return

# ================= QUEUE ENGINE =================

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

def add_to_queue(group_id: int, link: str):
    GROUP_QUEUE.setdefault(group_id, []).append(link)

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
                        return text[ent.offset : ent.offset + ent.length]
        return None

    async def details(self, link: str):
        if "&" in link:
            link = link.split("&")[0]

        search = VideosSearch(link, limit=1)
        r = (await search.next())["result"][0]

        title = r["title"]
        duration_min = r["duration"]
        vidid = r["id"]
        thumb = r["thumbnails"][0]["url"].split("?")[0]
        duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0

        return title, duration_min, duration_sec, thumb, vidid

    # ===== PLAY ENTRY =====
    async def play(self, player, group_id: int, link: str):
        add_to_queue(group_id, link)

        # agar kuch play nahi ho raha → start queue
        if not GROUP_PLAYING.get(group_id):
            asyncio.create_task(process_queue(player, group_id))
