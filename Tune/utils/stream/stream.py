# Authored By Certified Coders © 2025
import os
from random import randint
from typing import Union

from pyrogram.types import InlineKeyboardMarkup

import config
from Tune import Carbon, YouTube, app
from Tune.core.call import StreamController
from Tune.misc import db
from Tune.utils.database import add_active_video_chat, is_active_chat
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
        return

    is_video = bool(video)
    forceplay = bool(forceplay)

    if forceplay:
        await StreamController.force_stop_stream(chat_id)

    # ===================== PLAYLIST =====================
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0

        for search in result:
            if count >= config.PLAYLIST_FETCH_LIMIT:
                break
            try:
                title, duration_min, duration_sec, thumb, vidid = await YouTube.details(search, True)
            except:
                continue

            if not duration_min or duration_sec > config.DURATION_LIMIT:
                continue

            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "audio",
                )
                pos = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:60]}\n{_['play_20']} {pos}\n\n"

            else:
                db[chat_id] = []

                # 🔥 API AUDIO STREAM
                try:
                    api_data = await YouTube.api_request(vidid)
                    audio_url = api_data["audio_url"]
                except:
                    raise AssistantErr(_["play_14"])

                await StreamController.join_call(
                    chat_id,
                    original_chat_id,
                    audio_url,
                    video=False,
                )

                await put_queue(
                    chat_id,
                    original_chat_id,
                    audio_url,
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "audio",
                )

                img = await get_thumb(vidid)
                btn = stream_markup(_, chat_id)
                sent = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{vidid}",
                        title[:23],
                        duration_min,
                        user_name,
                    ),
                    reply_markup=InlineKeyboardMarkup(btn),
                )
                db[chat_id][0]["mystic"] = sent
                db[chat_id][0]["markup"] = "stream"
                count += 1

        if count == 0:
            return

        link = await TuneBin(msg)
        carbon = await Carbon.generate(msg[:1200], randint(100, 999999))
        return await app.send_photo(
            original_chat_id,
            photo=carbon,
            caption=_["play_21"].format(count - 1, link),
            reply_markup=close_markup(_),
        )

    # ===================== YOUTUBE =====================
    elif streamtype == "youtube":
        vidid = result["vidid"]
        title = result["title"].title()
        duration_min = result["duration_min"]
        thumbnail = result["thumb"]

        # 🔥 API AUDIO STREAM ONLY
        try:
            api_data = await YouTube.api_request(vidid)
            audio_url = api_data["audio_url"]
        except Exception as e:
            print("API ERROR:", e)
            raise AssistantErr(_["play_14"])

        if not audio_url:
            raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                audio_url,
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "audio",
            )
            pos = len(db.get(chat_id)) - 1
            return await app.send_message(
                original_chat_id,
                _["queue_4"].format(pos, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)),
            )

        db[chat_id] = []

        await StreamController.join_call(
            chat_id,
            original_chat_id,
            audio_url,
            video=False,
        )

        await put_queue(
            chat_id,
            original_chat_id,
            audio_url,
            title,
            duration_min,
            user_name,
            vidid,
            user_id,
            "audio",
            forceplay=forceplay,
        )

        img = await get_thumb(vidid)
        btn = stream_markup(_, chat_id)
        sent = await app.send_photo(
            original_chat_id,
            photo=img,
            caption=_["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{vidid}",
                title[:23],
                duration_min,
                user_name,
            ),
            reply_markup=InlineKeyboardMarkup(btn),
        )
        db[chat_id][0]["mystic"] = sent
        db[chat_id][0]["markup"] = "stream"

    # ===================== INDEX / M3U8 =====================
    elif streamtype == "index":
        link = result
        title = "Stream"
        duration_min = "00:00"

        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index",
                title,
                duration_min,
                user_name,
                link,
                "audio",
            )
            pos = len(db.get(chat_id)) - 1
            return await mystic.edit_text(
                _["queue_4"].format(pos, title, duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)),
            )

        db[chat_id] = []
        await StreamController.join_call(chat_id, original_chat_id, link, video=False)
        await put_queue_index(
            chat_id,
            original_chat_id,
            "index",
            title,
            duration_min,
            user_name,
            link,
            "audio",
            forceplay=forceplay,
        )

        sent = await app.send_photo(
            original_chat_id,
            photo=config.STREAM_IMG_URL,
            caption=_["stream_2"].format(user_name),
            reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
        )
        db[chat_id][0]["mystic"] = sent
        db[chat_id][0]["markup"] = "tg"
        await mystic.delete()
