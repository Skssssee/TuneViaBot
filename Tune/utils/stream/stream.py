# Authored By Certified Coders © 2025

from typing import Union
from random import randint
import os

from pyrogram.types import InlineKeyboardMarkup

import config
from Tune import Carbon, YouTube, app
from Tune.core.call import StreamController
from Tune.misc import db
from Tune.utils.database import is_active_chat, add_active_video_chat
from Tune.utils.exceptions import AssistantErr
from Tune.utils.inline import aq_markup, close_markup, stream_markup
from Tune.utils.pastebin import TuneBin
from Tune.utils.stream.queue import put_queue, put_queue_index
from Tune.utils.thumbnails import get_thumb
from Tune.utils.errors import capture_internal_err


@capture_internal_err
async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
):

    if not result:
        raise AssistantErr(_["play_14"])

    is_video = bool(video)
    forceplay = bool(forceplay)

    if forceplay:
        await StreamController.force_stop_stream(chat_id)

    # ======================================================
    # 🎵 YOUTUBE STREAM (WITH API FALLBACK)
    # ======================================================
    if streamtype == "youtube":
        vidid = result["vidid"]
        title = result["title"].title()
        duration_min = result["duration_min"]
        thumbnail = result["thumb"]

        file_path = None
        direct = False

        # 1️⃣ Try normal YouTube.download (yt-dlp)
        try:
            file_path, direct = await YouTube.download(
                vidid,
                mystic,
                video=is_video,
                videoid=True,
            )
        except Exception:
            file_path = None

        # 2️⃣ 🔥 FALLBACK → yt-api HLS audio (MOST IMPORTANT FIX)
        if not file_path:
            try:
                api_data = await YouTube.api_stream(vidid)
                file_path = api_data.get("audio_url")
                direct = True
            except Exception:
                raise AssistantErr(_["play_14"])

        if not file_path:
            raise AssistantErr(_["play_14"])

        # ================= QUEUE MODE =================
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            return await app.send_message(
                original_chat_id,
                _["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)),
            )

        # ================= START STREAM =================
        if not forceplay:
            db[chat_id] = []

        await StreamController.join_call(
            chat_id,
            original_chat_id,
            file_path,
            video=is_video,
            image=thumbnail,
        )

        await put_queue(
            chat_id,
            original_chat_id,
            file_path,
            title,
            duration_min,
            user_name,
            vidid,
            user_id,
            "video" if is_video else "audio",
            forceplay=forceplay,
        )

        img = await get_thumb(vidid)
        run = await app.send_photo(
            original_chat_id,
            photo=img,
            caption=_["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{vidid}",
                title[:23],
                duration_min,
                user_name,
            ),
            reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
        )

        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "stream"
        return

    # ======================================================
    # 📡 INDEX / M3U8 STREAM
    # ======================================================
    if streamtype == "index":
        link = result
        title = "Index Stream"
        duration_min = "∞"

        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if is_video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            return await mystic.edit_text(
                _["queue_4"].format(position, title, duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)),
            )

        if not forceplay:
            db[chat_id] = []

        await StreamController.join_call(
            chat_id,
            original_chat_id,
            link,
            video=is_video,
        )

        await put_queue_index(
            chat_id,
            original_chat_id,
            "index_url",
            title,
            duration_min,
            user_name,
            link,
            "video" if is_video else "audio",
            forceplay=forceplay,
        )

        run = await app.send_photo(
            original_chat_id,
            photo=config.STREAM_IMG_URL,
            caption=_["stream_2"].format(user_name),
            reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
        )

        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "tg"
        await mystic.delete()
        return

    # ======================================================
    # ❌ UNSUPPORTED TYPE
    # ======================================================
    raise AssistantErr(_["play_14"])
