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
) -> None:

    if not result:
        return

    is_video = bool(video)
    forceplay = bool(forceplay)

    if forceplay:
        await StreamController.force_stop_stream(chat_id)

    # ================= PLAYLIST =================
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0

        for search in result:
            if count >= config.PLAYLIST_FETCH_LIMIT:
                break
            try:
                title, duration_min, duration_sec, thumb, vidid = await YouTube.details(
                    search, videoid=True
                )
            except Exception:
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
                    "video" if is_video else "audio",
                )
                pos = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n{_['play_20']} {pos}\n\n"

            else:
                if not forceplay:
                    db[chat_id] = []

                try:
                    file_path, direct = await YouTube.download(
                        vidid, mystic, video=is_video, videoid=True
                    )
                except Exception:
                    raise AssistantErr(_["play_14"])

                if not file_path:
                    raise AssistantErr(_["play_14"])

                await StreamController.join_call(
                    chat_id,
                    original_chat_id,
                    file_path,
                    video=is_video,
                    image=thumb,
                )

                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path if direct else f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if is_video else "audio",
                    forceplay=forceplay,
                )

                img = await get_thumb(vidid)
                btn = stream_markup(_, chat_id)
                run = await app.send_photo(
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
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

        if count == 0:
            return

        link = await TuneBin(msg)
        lines = msg.count("\n")
        car = os.linesep.join(msg.split(os.linesep)[:17]) if lines > 17 else msg
        carbon = await Carbon.generate(car, randint(100, 9999999))
        return await app.send_photo(
            original_chat_id,
            photo=carbon,
            caption=_["play_21"].format(len(db.get(chat_id)) - 1, link),
            reply_markup=close_markup(_),
        )

    # ================= YOUTUBE =================
    elif streamtype == "youtube":
        vidid = result["vidid"]
        title = result["title"].title()
        duration_min = result["duration_min"]
        thumb = result["thumb"]

        try:
            # 🔥 STABLE METHOD (NO api_stream)
            file_path, direct = await YouTube.download(
                vidid, mystic, video=is_video, videoid=True
            )
        except Exception:
            raise AssistantErr(_["play_14"])

        if not file_path:
            raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
            )
            pos = len(db.get(chat_id)) - 1
            await app.send_message(
                original_chat_id,
                _["queue_4"].format(pos, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(aq_markup(_, chat_id)),
            )
        else:
            if not forceplay:
                db[chat_id] = []

            await StreamController.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=is_video,
                image=thumb,
            )

            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
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

    # ================= TELEGRAM FILE =================
    elif streamtype == "telegram":
        file_path = result["path"]
        title = result["title"].title()
        duration_min = result["dur"]

        if not file_path:
            raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                "telegram",
                user_id,
                "video" if is_video else "audio",
            )
        else:
            if not forceplay:
                db[chat_id] = []

            await StreamController.join_call(
                chat_id, original_chat_id, file_path, video=is_video
            )
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                "telegram",
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
            )

            if is_video:
                await add_active_video_chat(chat_id)

    # ================= INDEX / M3U8 =================
    elif streamtype == "index":
        link = result
        title = "INDEX / M3U8"

        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                "00:00",
                user_name,
                link,
                "video" if is_video else "audio",
            )
        else:
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
                "00:00",
                user_name,
                link,
                "video" if is_video else "audio",
                forceplay=forceplay,
                )
