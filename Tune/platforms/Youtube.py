
import asyncio
import os
import re
from typing import Union
import yt_dlp
from py_yt import VideosSearch
from Tune.utils.formatters import time_to_seconds
import aiohttp
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType

# --- CONFIGURATION ---
# ✅ REPLACE THIS WITH YOUR NEW KOYEB URL
MY_API_URL = "https://disabled-rosalinde-uhhy5-523ef0f0.koyeb.app" 
# ---------------------

async def get_video_id(link: str) -> str:
    """Helper to safely extract video ID from any YouTube link."""
    if "youtu.be" in link:
        return link.split("/")[-1].split("?")[0]
    elif "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    else:
        # If it's already just an ID or unknown format, return as is
        return link

async def download_song(link: str) -> str:
    video_id = await get_video_id(link)
    
    if not video_id:
        return None

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")

    # Check if already downloaded
    if os.path.exists(file_path):
        return file_path

    # Use the API
    api_url = MY_API_URL
    try:
        async with aiohttp.ClientSession() as session:
            # Construct the full YouTube URL for the API
            full_yt_url = f"https://www.youtube.com/watch?v={video_id}"
            stream_url = f"{api_url}/audio?url={full_yt_url}"
            
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            
            async with session.get(stream_url, headers=headers) as response:
                if response.status == 200:
                    with open(file_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(16384):
                            f.write(chunk)
                    
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                        return file_path
                else:
                    print(f"❌ API Error: {response.status}")
    except Exception as e:
        print(f"❌ Download Exception: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
    
    return None

async def download_video(link: str) -> str:
    video_id = await get_video_id(link)

    if not video_id:
        return None

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")

    if os.path.exists(file_path):
        return file_path

    api_url = MY_API_URL
    try:
        async with aiohttp.ClientSession() as session:
            full_yt_url = f"https://www.youtube.com/watch?v={video_id}"
            stream_url = f"{api_url}/download?url={full_yt_url}"
            
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            
            async with session.get(stream_url, headers=headers) as response:
                if response.status == 200:
                    with open(file_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(16384):
                            f.write(chunk)
                    
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                        return file_path
    except Exception as e:
        print(f"❌ Video Download Error: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
    
    return None

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    if "dash" not in str(format["format"]).lower():
                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format.get("filesize"),
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format["format_note"],
                                "yturl": link,
                            }
                        )
                except:
                    continue
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

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
    ) -> str:
        if videoid:
            link = self.base + link

        try:
            if video:
                downloaded_file = await download_video(link)
            else:
                downloaded_file = await download_song(link)
            
            if downloaded_file:
                return downloaded_file, True
            else:
                return None, False
        except Exception:
            return None, False
