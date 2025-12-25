import re
import aiohttp
from typing import Union

from Tune.utils.formatters import time_to_seconds

try:
    from py_yt import VideosSearch
except ImportError:
    from youtubesearchpython.__future__ import VideosSearch


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        # yt-api service running on same VPS
        self.api_base = "http://152.42.187.207:8000"

    # --------------------------------------------------
    # BASIC CHECK
    # --------------------------------------------------
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    # --------------------------------------------------
    # SEARCH / DETAILS
    # --------------------------------------------------
    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(link, limit=1)
        data = await results.next()

        if not data or not data.get("result"):
            raise Exception("No results found")

        r = data["result"][0]

        title = r["title"]
        duration_min = r.get("duration")
        thumbnail = r["thumbnails"][0]["url"].split("?")[0]
        vidid = r["id"]

        duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0

        return title, duration_min, duration_sec, thumbnail, vidid

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link

        if "&" in link:
            link = link.split("&")[0]

        results = VideosSearch(link, limit=1)
        data = await results.next()

        if not data or not data.get("result"):
            raise Exception("Track not found")

        r = data["result"][0]

        track = {
            "title": r["title"],
            "link": r["link"],
            "vidid": r["id"],
            "duration_min": r.get("duration"),
            "thumb": r["thumbnails"][0]["url"].split("?")[0],
        }

        return track, r["id"]

    # --------------------------------------------------
    # 🔥 MAIN API STREAM (NO DOWNLOAD, NO STORAGE)
    # --------------------------------------------------
    async def api_request(self, vidid: str):
        """
        Calls yt-api and returns audio stream URL
        """
        api_url = f"{self.api_base}/audio?url=https://youtu.be/{vidid}"
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    raise Exception("YT-API HTTP error")

                data = await resp.json()

                if not data or "audio_url" not in data:
                    raise Exception("audio_url missing in API response")

                return data

    # --------------------------------------------------
    # USED BY stream.py
    # --------------------------------------------------
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
        IMPORTANT:
        - No yt-dlp
        - No file download
        - Returns direct streaming URL
        """

        vidid = link if videoid else link.split("v=")[-1]

        api_data = await self.api_request(vidid)

        # pytgcalls accepts direct URL
        return api_data["audio_url"], True

    # --------------------------------------------------
    # LIVE VIDEO (SAFE)
    # --------------------------------------------------
    async def video(self, link: str):
        """
        Used only for live streams
        """
        vidid = link.split("v=")[-1]
        api_data = await self.api_request(vidid)
        return 1, api_data["audio_url"]
