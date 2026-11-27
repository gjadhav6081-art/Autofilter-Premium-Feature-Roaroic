# ─────────────────────────────────────────────
# Powered by Roaroic | Developer Channel: @roaroic0
# https://t.me/roaroic0
# ─────────────────────────────────────────────
import re
import logging
import asyncio
import aiohttp
from datetime import datetime
from collections import defaultdict
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps
from plugins.Roaroicfutures.Imdbposter import get_movie_detailsx, fetch_image, get_movie_details
from database.users_chats_db import db
from pyrogram import Client, filters, enums
from info import CHANNELS, MOVIE_UPDATE_CHANNEL, LINK_PREVIEW, ABOVE_PREVIEW, BAD_WORDS, LANDSCAPE_POSTER, TMDB_POSTER, ADMINS, BOT_TOKEN
from Script import script
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from utils import temp
from pymongo.errors import PyMongoError, DuplicateKeyError
from pyrogram.errors import MessageIdInvalid, MessageNotModified, FloodWait
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Precomputed sets for faster lookups
IGNORE_WORDS = {
    "rarbg", "dub", "sub", "sample", "mkv", "aac", "combined",
    "action", "adventure", "animation", "biography", "comedy", "crime", 
    "documentary", "drama", "family", "fantasy", "film-noir", "history", 
    "horror", "music", "musical", "mystery", "romance", "sci-fi", "sport", 
    "thriller", "war", "western", "hdcam", "hdtc", "camrip", "ts", "tc", 
    "telesync", "dvdscr", "dvdrip", "predvd", "webrip", "web-dl", "tvrip", 
    "hdtv", "web dl", "webdl", "bluray", "brrip", "bdrip", "360p", "480p", 
    "720p", "1080p", "2160p", "4k", "1440p", "540p", "240p", "140p", "hevc", 
    "hdrip", "hin", "hindi", "tam", "tamil", "kan", "kannada", "tel", "telugu", 
    "mal", "malayalam", "eng", "english", "pun", "punjabi", "ben", "bengali", 
    "mar", "marathi", "guj", "gujarati", "urd", "urdu", "kor", "korean", "jpn", 
    "japanese", "nf", "netflix", "sonyliv", "sony", "sliv", "amzn", "prime", 
    "primevideo", "hotstar", "zee5", "jio", "jhs", "aha", "hbo", "paramount", 
    "apple", "hoichoi", "sunnxt", "viki"
}|BAD_WORDS

# Constants
CAPTION_LANGUAGES = {
    "hin": "Hindi", "hindi": "Hindi",
    "tam": "Tamil", "tamil": "Tamil",
    "kan": "Kannada", "kannada": "Kannada",
    "tel": "Telugu", "telugu": "Telugu",
    "mal": "Malayalam", "malayalam": "Malayalam",
    "eng": "English", "english": "English",
    "pun": "Punjabi", "punjabi": "Punjabi",
    "ben": "Bengali", "bengali": "Bengali",
    "mar": "Marathi", "marathi": "Marathi",
    "guj": "Gujarati", "gujarati": "Gujarati",
    "urd": "Urdu", "urdu": "Urdu",
    "kor": "Korean", "korean": "Korean",
    "jpn": "Japanese", "japanese": "Japanese",
}

OTT_PLATFORMS = {
    "nf": "Netflix", "netflix": "Netflix",
    "sonyliv": "SonyLiv", "sony": "SonyLiv", "sliv": "SonyLiv",
    "amzn": "Amazon Prime Video", "prime": "Amazon Prime Video", "primevideo": "Amazon Prime Video",
    "hotstar": "Disney+ Hotstar", "zee5": "Zee5",
    "jio": "JioHotstar", "jhs": "JioHotstar",
    "aha": "Aha", "hbo": "HBO Max", "paramount": "Paramount+",
    "apple": "Apple TV+", "hoichoi": "Hoichoi", "sunnxt": "Sun NXT", "viki": "Viki"
}

STANDARD_GENRES = {
    'Action', 'Adventure', 'Animation', 'Biography', 'Comedy', 'Crime', 'Documentary',
    'Drama', 'Family', 'Fantasy', 'Film-Noir', 'History', 'Horror', 'Music',
    'Musical', 'Mystery', 'Romance', 'Sci-Fi', 'Sport', 'Thriller', 'War', 'Western'
}

# Precompiled regex patterns
CLEAN_PATTERN = re.compile(r'@[^ \n\r\t\.,:;!?()\[\]{}<>\\/"\'=_%]+|\bwww\.[^\s\]\)]+|\([\@^]+\)|\[[\@^]+\]')
NORMALIZE_PATTERN = re.compile(r"[._]+|[()\[\]{}:;'–!,.?_]")
QUALITY_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:ORG|HDCAM|HDTC|CAMRIP|TELESYNC|TS|TC|DVDSCR|DVDRIP|PREDVD|"
    r"WEBRIP|WEB[- ]?DL|WEBDL|TVRIP|HDTV|BLURAY|BRRIP|BDRIP|HDRIP|REMUX|"
    r"360P|480P|540P|720P|1080P|1440P|2160P|240P|140P|4K|8K|"
    r"HEVC|H\s*\.\s*265|H265|X265|H\s*\.\s*264|H264|X264|AV1|"
    r"8BIT|10BIT|HDR10|HDR|SDR|PROPER|REPACK)(?![A-Za-z0-9])",
    re.IGNORECASE
)
YEAR_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:19|20)\d{2}(?![A-Za-z0-9])")
RANGE_REGEX = re.compile(r'\bS(\d{1,2})[^\w\n\r]*E(?:p(?:isode)?)?0*(\d{1,2})\s*(?:to|-)\s*(?:E(?:p(?:isode)?)?)?0*(\d{1,2})',re.IGNORECASE)
SINGLE_REGEX = re.compile(r'\bS(\d{1,2})[^\w\n\r]*E(?:p(?:isode)?)?0*(\d{1,3})', re.IGNORECASE)
NAMED_REGEX = re.compile(r'Season\s*0*(\d{1,2})[\s\-,:]*Ep(?:isode)?\s*0*(\d{1,3})', re.IGNORECASE)
EP_ONLY_RANGE = re.compile(r'\b(?:EP|Episode)0*(\d{1,3})\s*-\s*0*(\d{1,3})\b',re.IGNORECASE)


MEDIA_FILTER = filters.document | filters.video | filters.audio
locks = defaultdict(asyncio.Lock)
pending_updates = {}


def clean_mentions_links(text: str) -> str:
    return CLEAN_PATTERN.sub("", text or "").strip()

def normalize(s: str) -> str:
    s = NORMALIZE_PATTERN.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()

def remove_ignored_words(text: str) -> str:
    IGNORE_WORDS_LOWER = {w.lower() for w in IGNORE_WORDS}
    return " ".join(word for word in text.split() if word.lower() not in IGNORE_WORDS_LOWER)

def format_quality_label(value: str) -> str:
    value = str(value).strip()
    # Keep resolution notation like 1080p/480p, uppercase codec and source labels.
    if re.fullmatch(r"\d{3,4}p", value, flags=re.IGNORECASE):
        return value.lower()
    return value.upper()


def get_qualities(*texts: str) -> str:
    """Collect every recognized quality/source tag from filename and caption."""
    formatted = []
    for text in texts:
        for quality in QUALITY_PATTERN.findall(str(text or "")):
            label = format_quality_label(quality)
            if label and label not in formatted:
                formatted.append(label)
    return ", ".join(formatted) if formatted else "N/A"

def format_uploaded_duration(seconds):
    """Format the duration reported by Telegram for the actual uploaded media."""
    try:
        total_minutes = int(seconds) // 60
    except (TypeError, ValueError):
        return None
    if total_minutes <= 0:
        return None
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m" if hours and minutes else (f"{hours}h" if hours else f"{minutes}m")


def format_runtime(value):
    """Normalize IMDb/TMDB runtime values, including ISO-8601 and TV episode runtimes."""
    if value in (None, "", "N/A"):
        return None
    if isinstance(value, (list, tuple, set)):
        for item in value:
            formatted = format_runtime(item)
            if formatted:
                return formatted
        return None
    if isinstance(value, (int, float)):
        total_minutes = int(value)
    else:
        raw = str(value).strip()
        if not raw or raw.upper() == "N/A":
            return None

        # ISO-8601 duration, e.g. PT1H53M.
        iso = re.fullmatch(r"(?i)PT(?:(\d+)H)?(?:(\d+)M)?", raw)
        if iso:
            total_minutes = int(iso.group(1) or 0) * 60 + int(iso.group(2) or 0)
        else:
            # Human-readable duration, e.g. "1 hour 53 minutes" or "1h 53m".
            hours_match = re.search(r"(?i)(\d+)\s*(?:h|hours?)\b", raw)
            minutes_match = re.search(r"(?i)(\d+)\s*(?:m|min|mins|minutes?)\b", raw)
            if hours_match or minutes_match:
                total_minutes = int(hours_match.group(1) if hours_match else 0) * 60
                total_minutes += int(minutes_match.group(1) if minutes_match else 0)
            else:
                # IMDb can return multiple runtimes like "113, 110"; use first.
                match = re.search(r"\b(\d{1,3})\b", raw)
                if not match:
                    return None
                total_minutes = int(match.group(1))

    if total_minutes <= 0:
        return None
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m" if hours and minutes else (f"{hours}h" if hours else f"{minutes}m")

def extract_ott_platform(text: str) -> str:
    # OTT availability must never be guessed from filenames/captions.
    # The only trusted source is TMDB's India watch-provider endpoint.
    return "N/A"


def extract_languages(filename: str, caption: str = "") -> str:
    source = f"{filename or ''} {caption or ''}".lower()
    found = {
        CAPTION_LANGUAGES[key]
        for key in CAPTION_LANGUAGES
        if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", source)
    }
    return ", ".join(sorted(found)) if found else "N/A"

def extract_season_episode(filename: str) -> Tuple[Optional[int], Optional[str]]:
    if m := EP_ONLY_RANGE.search(filename):
        return 1, f"{int(m.group(1))}-{int(m.group(2))}"
    for pattern in (RANGE_REGEX, SINGLE_REGEX, NAMED_REGEX):
        if m := pattern.search(filename):
            season = int(m.group(1))
            if pattern == RANGE_REGEX:
                ep = f"{m.group(2)}-{m.group(3)}"
            else:
                ep = m.group(2)
            return season, ep
    return None, None

def schedule_update(bot, base_name, delay=5):
    if handle := pending_updates.get(base_name):
        if not handle.cancelled():
            handle.cancel()
    
    loop = asyncio.get_event_loop()
    pending_updates[base_name] = loop.call_later(
        delay,
        lambda: asyncio.create_task(update_movie_message(bot, base_name))
    )

def extract_media_info(filename: str, caption: str):
    filename = normalize(clean_mentions_links(filename).title())
    caption_clean = clean_mentions_links(caption).lower() if caption else ""
    unified = f"{caption_clean} {filename.lower()}".strip()

    season = episode = year = None
    tag = "#MOVIE"
    processed_raw = base_raw = filename
    quality = get_qualities(filename, caption_clean)
    ott_platform = "N/A"  # Filled only from verified TMDB India streaming providers.

    language = extract_languages(filename, caption_clean)

    season, episode = extract_season_episode(filename)
    if season is not None:
        tag = "#SERIES"
        if m := (RANGE_REGEX.search(filename) or SINGLE_REGEX.search(filename) or NAMED_REGEX.search(filename) or EP_ONLY_RANGE.search(filename)):
            match_str = m.group(0)
            start_idx = filename.lower().find(match_str.lower())
            end_idx = start_idx + len(match_str)
            processed_raw = filename[:end_idx]
            base_raw = filename[:start_idx]
            if year_match := YEAR_PATTERN.search(filename.lower()[end_idx:]):
                y = year_match.group(0)
                yi = filename.lower().find(y, end_idx)
                if yi != -1:
                    processed_raw = filename[:yi+4]
                    base_raw += f" {y}"
    else:
        if year_match := YEAR_PATTERN.search(unified):
            year = year_match.group(0)
            year_idx = filename.lower().find(year.lower())
            if year_idx != -1:
                processed_raw = filename[:year_idx + 4]
                base_raw = processed_raw
        else:
            if qual_match := QUALITY_PATTERN.search(unified):
                qual_str = qual_match.group(0)
                qual_idx = filename.lower().find(qual_str.lower())
                if qual_idx != -1:
                    processed_raw = filename[:qual_idx]
                    base_raw = processed_raw

    base_name = normalize(remove_ignored_words(normalize(base_raw)))
    if year and year not in base_name:
        base_name += f" {year}"

    if base_name.endswith(")"):
        base_name = re.sub(r"\s+\(\d{4}\)$", "", base_name)
        if year:
            base_name += f" ({year})"

    return {
        "processed": normalize(processed_raw),
        "base_name": base_name,
        "tag": tag,
        "season": season,
        "episode": episode,
        "year": year,
        "quality": quality,
        "ott_platform": ott_platform,
        "language": language
    }

@Client.on_message(filters.chat(CHANNELS) & MEDIA_FILTER)
async def media_handler(bot, message):
    media = next(
        (getattr(message, ft) for ft in ("document", "video", "audio")
         if getattr(message, ft, None)),
        None
    )
    if not media:
        return

    media.file_type = next(ft for ft in ("document", "video", "audio") if hasattr(message, ft))
    media.caption = message.caption or ""
    # Telegram supplies the actual duration (seconds) for uploaded video/audio media.
    media.duration = getattr(media, "duration", None)
    success, info = await save_file(media)
    if not success:
        return

    try:
        if await db.movie_update_status(bot.me.id):
            await process_and_send_update(bot, media.file_name, media.caption, media.duration)
    except Exception:
        logger.exception("Error processing media")

async def process_and_send_update(bot, filename, caption, duration_seconds=None):
    try:
        media_info = extract_media_info(filename, caption)
        base_name = media_info["base_name"]
        processed = media_info["processed"]

        lock = locks[base_name]
        async with lock:
            await _process_with_lock(bot, filename, caption, media_info, base_name, processed, duration_seconds)
    except PyMongoError as e:
        logger.error("Database error: %s", e)
    except Exception as e:
        logger.exception("Processing failed: %s", e)

error_tmdb = False

async def _process_with_lock(bot, filename, caption, media_info, base_name, processed, duration_seconds=None):
    if not hasattr(db, 'movie_updates'):
        db.movie_updates = db.db.movie_updates

    movie_doc = await db.movie_updates.find_one({"_id": base_name})
    global error_tmdb
    error_tmdb=False
    file_data = {
        "filename": filename,
        "caption": caption or "",
        "processed": processed,
        "quality": media_info["quality"],
        "language": media_info["language"],
        "ott_platform": "N/A",
        "timestamp": datetime.now(),
        "tag": media_info["tag"],
        "season": media_info["season"],
        "episode": media_info["episode"],
        "duration_seconds": int(duration_seconds) if duration_seconds else None
    }

    if not movie_doc:
        # IMDb is the primary source for title details and artwork.
        imdb_details = await get_movie_details(base_name) or {}
        logger.info(
            "IMDb lookup for '%s': %s",
            base_name,
            "matched " + str(imdb_details.get("imdb_id")) if imdb_details else "no match"
        )
        # Query TMDB as a second source even when IMDb returns partial metadata.
        tmdb_details = await get_movie_detailsx(base_name) or {}
        logger.info(
            "TMDB lookup for '%s': %s",
            base_name,
            "matched " + str(tmdb_details.get("tmdb_id")) if tmdb_details.get("tmdb_id") else tmdb_details.get("error", "no match")
        )

        # IMDb has priority; TMDB fills every field IMDb does not provide.
        details = dict(tmdb_details)
        for key, value in imdb_details.items():
            if value not in (None, "", [], "N/A"):
                details[key] = value

        # Channel announcement must use the full-width TMDB landscape backdrop first.
        # Only fall back to portrait poster/IMDb artwork when TMDB has no backdrop.
        tmdb_backdrop = tmdb_details.get("backdrop_url")
        tmdb_poster = tmdb_details.get("poster_url")
        imdb_poster = imdb_details.get("poster_url")
        poster_url = tmdb_backdrop or tmdb_poster or imdb_poster
        backup_poster_url = next(
            (url for url in (tmdb_poster, imdb_poster) if url and url != poster_url),
            None
        )
        logger.info(
            "Announcement poster source for '%s': %s",
            base_name,
            "TMDB backdrop" if tmdb_backdrop and poster_url == tmdb_backdrop
            else "TMDB poster" if tmdb_poster and poster_url == tmdb_poster
            else "IMDb" if imdb_poster and poster_url == imdb_poster
            else "no provider artwork"
        )

        raw_genres = details.get("genres", "N/A")
        if isinstance(raw_genres, str):
            genres = ", ".join(g.strip() for g in raw_genres.split(",") if g.strip()) or "N/A"
        elif isinstance(raw_genres, (list, tuple, set)):
            genres = ", ".join(str(g).strip() for g in raw_genres if str(g).strip()) or "N/A"
        else:
            genres = "N/A"

        movie_doc = {
            "_id": base_name,
            "title": details.get("title") or imdb_details.get("title") or base_name,
            "files": [file_data],
            "poster_url": poster_url,
            "backup_poster_url": backup_poster_url,
            "is_landscape": True,
            "genres": genres,
            "rating": details.get("rating") or "N/A",
            "runtime": format_uploaded_duration(duration_seconds) or "N/A",
            "imdb_url": imdb_details.get("url") or (
                f"https://www.imdb.com/title/{imdb_details.get('imdb_id')}"
                if imdb_details.get("imdb_id") else
                details.get("tmdb_url") or ""
            ),
            "year": media_info["year"] or imdb_details.get("year") or tmdb_details.get("year"),
            "tag": media_info["tag"],
            "ott_platform": tmdb_details.get("ott_platform") or "N/A",
            "online_languages": (
                details.get("languages")
                if isinstance(details.get("languages"), str)
                else ", ".join(details.get("languages") or [])
            ),
            "message_id": None,
            "is_photo": False
        }
        try:
            await db.movie_updates.insert_one(movie_doc)
            await send_movie_update(bot, base_name)
            movie_doc = await db.movie_updates.find_one({"_id": base_name})
        except DuplicateKeyError:
            movie_doc = await db.movie_updates.find_one({"_id": base_name})
            if movie_doc:
                if any(f["filename"] == filename for f in movie_doc["files"]):
                    return
                await db.movie_updates.update_one(
                    {"_id": base_name},
                    {"$push": {"files": file_data}}
                )
                movie_doc["files"].append(file_data)
                schedule_update(bot, base_name)
    else:
        if any(f["filename"] == filename for f in movie_doc["files"]):
            return
        await db.movie_updates.update_one(
            {"_id": base_name},
            {"$push": {"files": file_data}}
        )
        movie_doc["files"].append(file_data)

        # Use the longest actual duration among every uploaded quality.
        known_durations = [
            int(item.get("duration_seconds") or 0)
            for item in movie_doc.get("files", [])
            if int(item.get("duration_seconds") or 0) > 0
        ]
        longest_duration = max(known_durations, default=0)
        longest_runtime = format_uploaded_duration(longest_duration)
        if longest_runtime and movie_doc.get("runtime") != longest_runtime:
            await db.movie_updates.update_one(
                {"_id": base_name},
                {"$set": {"runtime": longest_runtime}}
            )
            movie_doc["runtime"] = longest_runtime

        # Repair older movie records that were created without IMDb artwork/details.
        if (
            not movie_doc.get("poster_url")
            or movie_doc.get("genres") in (None, "", "N/A")
            or movie_doc.get("rating") in (None, "", "N/A")
            or movie_doc.get("runtime") in (None, "", "N/A")
            or movie_doc.get("ott_platform") in (None, "", "N/A")
            or movie_doc.get("online_languages") in (None, "", "N/A")
        ):
            imdb_details = await get_movie_details(base_name) or {}
            # Retry both providers for old database records missing poster/details.
            tmdb_details = await get_movie_detailsx(base_name) or {}
            if not isinstance(imdb_details, dict):
                imdb_details = {}
            if not isinstance(tmdb_details, dict) or tmdb_details.get("error"):
                logger.warning(
                    "TMDB metadata unavailable while repairing %s: %s",
                    base_name,
                    tmdb_details.get("error") if isinstance(tmdb_details, dict) else "invalid response"
                )
                tmdb_details = {}

            # Prefer the full-width TMDB landscape backdrop for announcement images.
            # Use portrait TMDB poster and then IMDb only if no backdrop exists.
            tmdb_backdrop = tmdb_details.get("backdrop_url")
            tmdb_poster = tmdb_details.get("poster_url")
            imdb_poster = imdb_details.get("poster_url")
            fresh_poster = tmdb_backdrop or tmdb_poster or imdb_poster
            poster_url = fresh_poster or movie_doc.get("poster_url") or movie_doc.get("backup_poster_url")
            logger.info(
                "Repair poster source for '%s': %s",
                base_name,
                "TMDB backdrop" if tmdb_backdrop and fresh_poster == tmdb_backdrop
                else "TMDB poster" if tmdb_poster and fresh_poster == tmdb_poster
                else "IMDb" if imdb_poster and fresh_poster == imdb_poster
                else "saved artwork/fallback"
            )
            updates = {}
            if poster_url:
                updates["poster_url"] = poster_url
                updates["backup_poster_url"] = next(
                    (url for url in (tmdb_backdrop, imdb_poster, movie_doc.get("backup_poster_url"))
                     if url and url != poster_url),
                    None
                )
            title_candidate = imdb_details.get("title") or tmdb_details.get("title")
            if title_candidate and not movie_doc.get("title"):
                updates["title"] = title_candidate
            for field in ("genres", "rating", "year"):
                current = movie_doc.get(field)
                candidate = imdb_details.get(field) or tmdb_details.get(field)
                if candidate and current in (None, "", "N/A"):
                    if field == "genres" and not isinstance(candidate, str):
                        candidate = ", ".join(str(item) for item in candidate)
                    updates[field] = candidate

            online_languages = tmdb_details.get("languages") or []
            if online_languages and movie_doc.get("online_languages") in (None, "", "N/A"):
                updates["online_languages"] = ", ".join(str(item) for item in online_languages)
            # Replace any legacy/guessed OTT value with verified India provider data.
            updates["ott_platform"] = tmdb_details.get("ott_platform") or "N/A"

            if imdb_details.get("url"):
                updates["imdb_url"] = imdb_details["url"]

            if updates:
                await db.movie_updates.update_one(
                    {"_id": base_name},
                    {"$set": updates}
                )
                movie_doc.update(updates)

                # Keep the existing channel post; metadata/artwork changes are
                # applied by editing that same post below.
        schedule_update(bot, base_name)

async def set_red_get_files_button(message_id, base_name, retries=3):
    """Re-apply Telegram's red button style after every announcement send/edit."""
    if not BOT_TOKEN or not message_id:
        logger.warning("Cannot apply red GET FILES button style: BOT_TOKEN/message_id missing.")
        return False

    reply_markup = {
        "inline_keyboard": [[{
            "text": "ɢᴇᴛ ғɪʟᴇs",
            "url": f"https://t.me/{temp.U_NAME}?start=getfile-{base_name.replace(' ', '-')}",
            "style": "danger"
        }]]
    }
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup"
    timeout = aiohttp.ClientTimeout(total=15)

    for attempt in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    api_url,
                    json={
                        "chat_id": MOVIE_UPDATE_CHANNEL,
                        "message_id": message_id,
                        "reply_markup": reply_markup
                    }
                ) as response:
                    result = await response.json(content_type=None)
                    description = str(result.get("description", "")).lower()

                    if response.status == 200 and result.get("ok"):
                        logger.info("Red GET FILES button confirmed on announcement %s", message_id)
                        return True

                    # Telegram returns this when the exact same red keyboard is already set.
                    if "message is not modified" in description:
                        logger.info("Red GET FILES button already active on announcement %s", message_id)
                        return True

                    logger.warning(
                        "Red GET FILES attempt %s/%s failed for %s: HTTP %s - %s",
                        attempt, retries, message_id, response.status, result
                    )
        except Exception:
            logger.exception(
                "Red GET FILES attempt %s/%s raised an error for announcement %s",
                attempt, retries, message_id
            )

        if attempt < retries:
            await asyncio.sleep(attempt * 2)

    logger.error("Could not confirm red GET FILES button after %s attempts for %s", retries, message_id)
    return False


async def reapply_red_get_files_button_later(message_id, base_name):
    """Second pass catches a later keyboard overwrite from a closely timed edit."""
    await asyncio.sleep(2)
    await set_red_get_files_button(message_id, base_name)

async def send_movie_update(bot, base_name):
    max_retries = 3
    base_delay = 5
    for attempt in range(max_retries):
        try:
            movie_doc = await db.movie_updates.find_one({"_id": base_name})
            if not movie_doc:
                return None

            text = generate_movie_message(movie_doc, base_name)
            buttons = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    'ɢᴇᴛ ғɪʟᴇs',
                    url=f"https://t.me/{temp.U_NAME}?start=getfile-{base_name.replace(' ', '-')}"
                )
            ]])

            resized_poster = None
            # Try the IMDb image first, then TMDB artwork if the IMDb URL fails.
            poster_urls = [
                movie_doc.get("poster_url"),
                movie_doc.get("backup_poster_url")
            ]
            for poster_url in poster_urls:
                if not poster_url:
                    continue
                logger.info("Trying announcement artwork for '%s': %s", base_name, poster_url[:180])
                resized_poster = await fetch_image(
                    poster_url,
                    size=(1280, 720)
                )
                if resized_poster:
                    logger.info("Announcement artwork downloaded successfully for '%s'", base_name)
                    break
                logger.warning("Announcement artwork URL failed for '%s': %s", base_name, poster_url[:180])

            # fetch_image already returns 16:9; normalize once more for safety.
            if resized_poster:
                source_image = Image.open(resized_poster).convert("RGB")
                landscape_image = ImageOps.fit(
                    source_image, (1280, 720),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5)
                )
                output = BytesIO()
                landscape_image.save(output, format="JPEG", quality=92)
                output.seek(0)
                output.name = "movie_landscape.jpg"
                resized_poster = output
            else:
                logger.warning("IMDb/TMDB poster unavailable for '%s'; using branded fallback.", base_name)
                resized_poster = generate_fallback_poster(movie_doc, base_name)

            msg = await bot.send_photo(
                chat_id=MOVIE_UPDATE_CHANNEL,
                photo=resized_poster,
                caption=text,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.HTML
            )
            is_photo = True

            await db.movie_updates.update_one(
                {"_id": base_name},
                {"$set": {"message_id": msg.id, "is_photo": is_photo}}
            )
            await set_red_get_files_button(msg.id, base_name)
            asyncio.create_task(reapply_red_get_files_button_later(msg.id, base_name))
            # Audit the saved data after the first post is visible, then edit that post.
            asyncio.create_task(verify_movie_post_after_send(bot, base_name))
            return msg
        except FloodWait as e:
            wait_time = e.value + 2
            await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"Failed to send movie update: {e}")
            break
    return None

async def update_movie_message(bot, base_name):
    try:
        movie_doc = await db.movie_updates.find_one({"_id": base_name})
        if not movie_doc:
            return

        text = generate_movie_message(movie_doc, base_name)
        buttons = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                'ɢᴇᴛ ғɪʟᴇs',
                url=f"https://t.me/{temp.U_NAME}?start=getfile-{base_name.replace(' ', '-')}"
            )
        ]])

        message_id = movie_doc.get("message_id")
        is_photo = movie_doc.get("is_photo", False)

        if not message_id:
            await send_movie_update(bot, base_name)
            return

        try:
            if is_photo:
                # Refresh the actual poster media as well as its caption.
                # Editing only the caption leaves an old/fallback thumbnail in place.
                resized_poster = None
                for poster_url in (
                    movie_doc.get("poster_url"),
                    movie_doc.get("backup_poster_url")
                ):
                    if not poster_url:
                        continue
                    resized_poster = await fetch_image(
                        poster_url,
                        size=(1280, 720)
                    )
                    if resized_poster:
                        break

                if not resized_poster:
                    # Never leave a photo announcement without artwork after refresh.
                    resized_poster = generate_fallback_poster(movie_doc, base_name)

                media = InputMediaPhoto(
                    media=resized_poster,
                    caption=text,
                    parse_mode=enums.ParseMode.HTML
                )
                await bot.edit_message_media(
                    chat_id=MOVIE_UPDATE_CHANNEL,
                    message_id=message_id,
                    media=media,
                    reply_markup=buttons
                )
                await set_red_get_files_button(message_id, base_name)
                asyncio.create_task(reapply_red_get_files_button_later(message_id, base_name))
            else:
                # Telegram cannot turn a text message into a photo by editing it.
                # Upgrade legacy text-only announcements by sending the photo first,
                # then remove the old bot message only after the new post succeeds.
                resized_poster = None
                for poster_url in (
                    movie_doc.get("poster_url"),
                    movie_doc.get("backup_poster_url")
                ):
                    if not poster_url:
                        continue
                    resized_poster = await fetch_image(
                        poster_url,
                        size=(1280, 720)
                    )
                    if resized_poster:
                        break

                if not resized_poster:
                    resized_poster = generate_fallback_poster(movie_doc, base_name)

                new_msg = await bot.send_photo(
                    chat_id=MOVIE_UPDATE_CHANNEL,
                    photo=resized_poster,
                    caption=text,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )
                await db.movie_updates.update_one(
                    {"_id": base_name},
                    {"$set": {"message_id": new_msg.id, "is_photo": True}}
                )
                await set_red_get_files_button(new_msg.id, base_name)
                asyncio.create_task(reapply_red_get_files_button_later(new_msg.id, base_name))
                # Keep the old text-only announcement in channel history.
                # The database now points to the new photo announcement.
            return
        except MessageNotModified:
            await set_red_get_files_button(message_id, base_name)
            asyncio.create_task(reapply_red_get_files_button_later(message_id, base_name))
            return
        except MessageIdInvalid:
            logger.warning(
                "Stored announcement message %s for %s is no longer valid; "
                "creating a replacement announcement.",
                message_id, base_name
            )
            # The saved Telegram message no longer exists or cannot be edited.
            # Clear the stale ID so the normal sender creates a fresh 16:9 post
            # and stores its new message ID for subsequent quality updates.
            await db.movie_updates.update_one(
                {"_id": base_name},
                {"$set": {"message_id": None, "is_photo": False}}
            )
            await send_movie_update(bot, base_name)
            return
        except Exception:
            logger.exception(
                "Could not edit existing announcement for %s; keeping the old post.",
                base_name
            )
            return
    except Exception as e:
        logger.error(f"Failed to update movie message: {e}")


async def verify_movie_post_after_send(bot, base_name):
    """Second-pass audit for fields missed during the initial announcement."""
    await asyncio.sleep(12)
    changed = False
    try:
        async with locks[base_name]:
            movie_doc = await db.movie_updates.find_one({"_id": base_name})
            if not movie_doc:
                return

            files = movie_doc.get("files", [])
            for item in files:
                filename = str(item.get("filename") or "")
                caption = str(item.get("caption") or "")
                quality = get_qualities(filename, caption)
                language = extract_languages(filename, caption)
                # Never infer OTT availability from an upload filename/caption.
                ott = "N/A"

                if quality != "N/A" and item.get("quality") != quality:
                    item["quality"] = quality
                    changed = True
                if language != "N/A" and item.get("language") != language:
                    item["language"] = language
                    changed = True
                if item.get("ott_platform") != "N/A":
                    item["ott_platform"] = "N/A"
                    changed = True

            # Prefer the actual uploaded media duration when available.
            durations = [int(x.get("duration_seconds") or 0) for x in files
                         if int(x.get("duration_seconds") or 0) > 0]
            if durations:
                runtime = format_uploaded_duration(max(durations))
                if runtime and movie_doc.get("runtime") != runtime:
                    movie_doc["runtime"] = runtime
                    changed = True

            # Always re-check OTT so old guessed/stale platform values are removed.
            missing = True
            if missing:
                imdb = await get_movie_details(base_name) or {}
                tmdb = await get_movie_detailsx(base_name) or {}
                if not isinstance(imdb, dict):
                    imdb = {}
                if not isinstance(tmdb, dict) or tmdb.get("error"):
                    tmdb = {}

                updates = {}
                for field in ("genres", "rating", "runtime", "ott_platform",
                              "languages", "poster_url", "year", "title"):
                    value = imdb.get(field)
                    if value in (None, "", [], "N/A"):
                        value = tmdb.get(field)
                    if value in (None, "", [], "N/A"):
                        continue
                    if field == "genres" and movie_doc.get("genres") in (None, "", "N/A"):
                        updates["genres"] = (", ".join(str(v) for v in value)
                                             if isinstance(value, (list, tuple, set)) else value)
                    elif field == "rating" and movie_doc.get("rating") in (None, "", "N/A"):
                        updates["rating"] = value
                    elif field == "runtime" and movie_doc.get("runtime") in (None, "", "N/A"):
                        formatted = format_runtime(value)
                        if formatted:
                            updates["runtime"] = formatted
                    elif field == "ott_platform":
                        # Only TMDB's India watch-provider result is authoritative.
                        updates["ott_platform"] = tmdb.get("ott_platform") or "N/A"
                    elif field == "languages" and movie_doc.get("online_languages") in (None, "", "N/A"):
                        updates["online_languages"] = (value if isinstance(value, str)
                                                       else ", ".join(str(v) for v in value))
                    elif field == "poster_url" and not movie_doc.get("poster_url"):
                        updates["poster_url"] = value
                        updates["is_landscape"] = True
                    elif field in ("year", "title") and not movie_doc.get(field):
                        updates[field] = value

                if updates:
                    movie_doc.update(updates)
                    changed = True

            if changed:
                save_fields = {
                    key: movie_doc[key]
                    for key in ("runtime", "genres", "rating", "ott_platform",
                                "online_languages", "poster_url", "is_landscape",
                                "year", "title")
                    if key in movie_doc
                }
                save_fields["files"] = files
                await db.movie_updates.update_one(
                    {"_id": base_name}, {"$set": save_fields}
                )

        if changed:
            logger.info("Second-pass audit repaired metadata for '%s'; editing original post.", base_name)
            await update_movie_message(bot, base_name)
        else:
            logger.info("Second-pass audit found no further metadata for '%s'.", base_name)
    except Exception:
        logger.exception("Second-pass audit failed for '%s'.", base_name)


async def sync_movie_updates_after_file_delete(bot, deleted_filenames):
    """Remove deleted database files from movie announcements and clean empty posts."""
    deleted_keys = {
        re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()
        for name in deleted_filenames if name
    }
    if not deleted_keys:
        return

    async for movie_doc in db.movie_updates.find({}):
        movie_files = movie_doc.get("files", [])
        remaining_files = [
            item for item in movie_files
            if re.sub(
                r"[^a-z0-9]+", " ",
                str(item.get("filename", "")).lower()
            ).strip() not in deleted_keys
        ]
        if len(remaining_files) == len(movie_files):
            continue

        base_name = movie_doc["_id"]
        pending = pending_updates.pop(base_name, None)
        if pending and not pending.cancelled():
            pending.cancel()

        if remaining_files:
            await db.movie_updates.update_one(
                {"_id": base_name},
                {"$set": {"files": remaining_files}}
            )
            await update_movie_message(bot, base_name)
            logger.info("Updated channel announcement after file deletion: %s", base_name)
            continue

        message_id = movie_doc.get("message_id")
        if message_id:
            try:
                await bot.delete_messages(
                    chat_id=MOVIE_UPDATE_CHANNEL,
                    message_ids=message_id
                )
            except MessageIdInvalid:
                pass
            except Exception:
                logger.exception(
                    "Could not delete channel announcement for %s", base_name
                )
                continue

        await db.movie_updates.delete_one({"_id": base_name})
        logger.info("Deleted empty movie announcement: %s", base_name)

def generate_fallback_poster(movie_doc, base_name):
    """Create a branded poster when TMDB/IMDb has no usable artwork."""
    width, height = 1280, 720
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)

    # Deep blue/purple vertical gradient with subtle geometric decoration.
    top = (12, 18, 38)
    bottom = (48, 20, 68)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = tuple(int(top[k] * (1 - ratio) + bottom[k] * ratio) for k in range(3))
        draw.line((0, y, width, y), fill=color)
    draw.ellipse((width - 310, 90, width + 160, 560), outline=(91, 75, 130), width=5)
    draw.ellipse((-190, 760, 300, 1250), outline=(75, 61, 112), width=5)
    draw.rounded_rectangle((42, 42, width - 42, height - 42), radius=28,
                           outline=(145, 125, 185), width=3)

    try:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        small_font = ImageFont.truetype(font_path, 28)
        title_font = ImageFont.truetype(font_path, 58)
        footer_font = ImageFont.truetype(font_path, 26)
    except Exception:
        small_font = title_font = footer_font = ImageFont.load_default()

    is_series = any(f.get("tag") == "#SERIES" for f in movie_doc.get("files", []))
    label = "NEW SERIES" if is_series else "NEW MOVIE"
    draw.text((width // 2, 145), label, font=small_font, fill=(230, 205, 255), anchor="mm")

    title = str(base_name or "Untitled").strip()
    words = title.split()
    lines, line = [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=title_font)[2] <= width - 130:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    if not lines:
        lines = ["Untitled"]
    # Keep long titles readable and inside the poster.
    if len(lines) > 5:
        lines = lines[:5]
        lines[-1] = lines[-1][:24] + "…"

    line_height = 76
    y = height // 2 - (len(lines) * line_height) // 2
    for title_line in lines:
        draw.text((width // 2, y), title_line, font=title_font,
                  fill=(255, 255, 255), anchor="mm", stroke_width=1,
                  stroke_fill=(30, 20, 45))
        y += line_height

    draw.line((300, 555, width - 300, 555), fill=(170, 145, 205), width=3)
    draw.text((width // 2, 615), "FILMS CHOR", font=footer_font,
              fill=(230, 205, 255), anchor="mm")
    output = BytesIO()
    image.save(output, format="JPEG", quality=92)
    output.seek(0)
    output.name = "movie_poster.jpg"
    return output


def generate_movie_message(movie_doc, base_name):
    all_qualities = set()
    all_languages = set()
    all_ott_platforms = set()
    all_tags = set()
    episodes_by_season = defaultdict(set)

    for file in movie_doc.get("files", []):
        # Re-check both the stored quality and original filename/caption-derived
        # text so older records and uploads with multiple tags are not missed.
        quality_source = " ".join(
            str(file.get(key) or "")
            for key in ("quality", "filename", "processed")
        )
        detected_qualities = get_qualities(quality_source)
        quality_values = (
            detected_qualities.split(",")
            if detected_qualities != "N/A"
            else str(file.get("quality") or "").split(",")
        )
        for quality in quality_values:
            quality = format_quality_label(quality.strip())
            if quality and quality != "N/A":
                all_qualities.add(quality)
        if file["language"] != "N/A":
            all_languages.update(l.strip() for l in file["language"].split(",") if l.strip())
        if file["ott_platform"] != "N/A":
            platforms = [p.strip() for p in file["ott_platform"].split("|") if p.strip()]
            all_ott_platforms.update(platforms)
        if file["tag"]:
            all_tags.add(file["tag"])
        if file.get("season") and file.get("episode"):
            season = file["season"]
            episode = file["episode"]
            episodes_by_season[season].add(episode)

    primary_tag = "#SERIES" if "#SERIES" in all_tags else "#MOVIE"
    epi_block = ""
    if episodes_by_season:
        episode_lines = []
        for season, episodes in sorted(episodes_by_season.items(), key=lambda x: int(x[0])):
            singles = []
            ranges = []

            for ep in episodes:
                if "-" in ep:
                    ranges.append(ep)
                else:
                    try:
                        singles.append(int(ep))
                    except ValueError:
                        ranges.append(ep)

            singles.sort()
            collapsed = []
            start = end = None
            for num in singles:
                if start is None:
                    start = end = num
                elif num == end + 1:
                    end = num
                else:
                    collapsed.append(str(start) if start == end else f"{start}-{end}")
                    start = end = num
            if start is not None:
                collapsed.append(str(start) if start == end else f"{start}-{end}")

            all_ep_parts = collapsed + sorted(ranges, key=lambda s: int(s.split("-")[0]))
            episode_lines.append(f"S{int(season)}: {', '.join(all_ep_parts)}")

        epi_str = ", ".join(episode_lines)
        if epi_str:
            epi_block = f"📺 ᴇᴘɪsᴏᴅᴇs : <b>{epi_str}</b>"

    genres = movie_doc.get("genres", "N/A")
    if isinstance(genres, (list, tuple, set)):
        genres = ", ".join(str(item) for item in genres if item) or "N/A"
    runtime = str(movie_doc.get("runtime") or "N/A")
    if runtime != "N/A":
        minute_match = re.fullmatch(r"\s*(\d+)\s*(?:minutes?|mins?|m)\s*", runtime, re.I)
        if minute_match:
            total_minutes = int(minute_match.group(1))
            hours, minutes = divmod(total_minutes, 60)
            runtime = f"{hours}h {minutes}m" if hours and minutes else (
                f"{hours}h" if hours else f"{minutes}m"
            )
        else:
            runtime = runtime.replace(" minutes", "m").replace(" minute", "m").replace(" min", "m")
            if runtime.isdigit():
                total_minutes = int(runtime)
                hours, minutes = divmod(total_minutes, 60)
                runtime = f"{hours}h {minutes}m" if hours and minutes else (
                    f"{hours}h" if hours else f"{minutes}m"
                )
    rating = str(movie_doc.get("rating") or "N/A")
    if rating != "N/A" and not rating.endswith("/10"):
        try:
            rating = f"{float(rating):.1f}/10"
        except (TypeError, ValueError):
            pass
    # Show resolution qualities first, highest to lowest, then source/codec labels.
    # Example: 1080p, 720p, 480p, WEB-DL, HEVC.
    def quality_sort_key(label):
        match = re.fullmatch(r"(\d{3,4})p", str(label).strip(), re.IGNORECASE)
        if match:
            return (0, -int(match.group(1)), "")
        return (1, 0, str(label).upper())

    quality_str = ", ".join(sorted(all_qualities, key=quality_sort_key)) if all_qualities else "N/A"
    language_str = ", ".join(sorted(all_languages)) if all_languages else "N/A"
    # Do not use file-level tags: they are not proof of streaming availability.
    ott_str = str(movie_doc.get("ott_platform") or "N/A").strip() or "N/A"
    if not all_languages:
        online_languages = movie_doc.get("online_languages")
        if online_languages:
            language_str = online_languages

    display_title = movie_doc.get("title") or base_name
    year = movie_doc.get("year")
    if year and str(year) not in str(display_title):
        display_title = f"{display_title} ({year})"

    return script.MOVIE_UPDATE_NOTIFY_TXT.format(
        poster_url=movie_doc.get("poster_url", ""),
        imdb_url=movie_doc.get("imdb_url", ""),
        filename=display_title,
        tag=primary_tag,
        genres=genres,
        runtime=runtime,
        ott=ott_str,
        quality=quality_str,
        language=language_str,
        episodes=epi_block,
        rating=rating,
        search_link=temp.B_LINK
    )


# Refresh task controls. The stop command leaves the current movie intact.
refresh_running = False
refresh_stop_requested = False


@Client.on_message(filters.command("refreshmovies") & filters.user(ADMINS))
async def refresh_all_movie_metadata(bot, message):
    """Admin utility: re-fetch IMDb/TMDB details and refresh existing channel posts."""
    global refresh_running, refresh_stop_requested

    if refresh_running:
        await message.reply_text("<b>⚠️ Refresh pehle se chal raha hai. Use /stoprefresh to stop it.</b>")
        return

    refresh_running = True
    refresh_stop_requested = False
    status = await message.reply_text(
        "<b>🔄 IMDb/TMDB se purani movies ki details aur posters refresh ho rahe hain...</b>"
    )
    if not hasattr(db, "movie_updates"):
        db.movie_updates = db.db.movie_updates

    checked = updated = posted = failed = post_failed = 0
    stopped = False
    refresh_state = db.db["movie_refresh_state"]
    saved_state = await refresh_state.find_one({"_id": "metadata_refresh"})
    last_id = (
        saved_state.get("last_id")
        if saved_state and not saved_state.get("completed")
        else None
    )
    resume_query = {"_id": {"$gt": last_id}} if last_id else {}
    if last_id:
        await status.edit_text(
            f"<b>⏯️ Refresh saved position se resume ho raha hai...\\nLast completed: {last_id}</b>"
        )
    else:
        await status.edit_text(
            "<b>🔄 IMDb/TMDB se purani movies ki details aur posters refresh ho rahe hain...</b>"
        )

    async def save_refresh_checkpoint(movie_id):
        await refresh_state.update_one(
            {"_id": "metadata_refresh"},
            {"$set": {"last_id": movie_id, "completed": False}},
            upsert=True
        )

    def has_value(value):
        return value not in (None, "", [], {}, "N/A", "n/a")

    def first_value(*values):
        return next((value for value in values if has_value(value)), None)

    try:
        async for movie_doc in db.movie_updates.find(resume_query).sort("_id", 1):
            if refresh_stop_requested:
                stopped = True
                break

            base_name = movie_doc.get("_id")
            if not base_name:
                continue

            checked += 1
            try:
                # Query both sources independently. One provider failing must not
                # prevent valid metadata from the other provider being refreshed.
                imdb_details = await get_movie_details(base_name)
                tmdb_details = await get_movie_detailsx(base_name)

                if not isinstance(imdb_details, dict) or imdb_details.get("error"):
                    imdb_details = {}
                if not isinstance(tmdb_details, dict) or tmdb_details.get("error"):
                    logger.warning(
                        "TMDB metadata unavailable for %s: %s",
                        base_name,
                        tmdb_details.get("error") if isinstance(tmdb_details, dict) else "invalid response"
                    )
                    tmdb_details = {}

                if refresh_stop_requested:
                    stopped = True
                    break

                # Prefer IMDb for IMDb-specific fields; use TMDB to fill gaps.
                # This avoids a blank/partial provider response erasing good data.
                title = first_value(imdb_details.get("title"), tmdb_details.get("title"), movie_doc.get("title"), base_name)
                raw_genres = first_value(imdb_details.get("genres"), tmdb_details.get("genres"))
                if isinstance(raw_genres, (list, tuple, set)):
                    genres = ", ".join(str(item) for item in raw_genres if item)
                elif isinstance(raw_genres, str):
                    genres = raw_genres.strip()
                else:
                    genres = None

                raw_languages = first_value(imdb_details.get("languages"), tmdb_details.get("languages"))
                if isinstance(raw_languages, (list, tuple, set)):
                    online_languages = ", ".join(str(item) for item in raw_languages if item)
                elif isinstance(raw_languages, str):
                    online_languages = raw_languages.strip()
                else:
                    online_languages = None

                runtime = format_runtime(first_value(
                    imdb_details.get("runtime"),
                    tmdb_details.get("runtime"),
                    tmdb_details.get("episode_run_time")
                ))
                old_runtime = format_runtime(movie_doc.get("runtime"))

                # Always prefer the landscape TMDB backdrop for channel artwork.
                tmdb_backdrop = tmdb_details.get("backdrop_url")
                tmdb_poster = tmdb_details.get("poster_url")
                imdb_poster = imdb_details.get("poster_url")
                poster_url = first_value(
                    tmdb_backdrop, tmdb_poster, imdb_poster,
                    movie_doc.get("poster_url"), movie_doc.get("backup_poster_url")
                )
                logger.info(
                    "Refresh poster source for '%s': %s",
                    base_name,
                    "TMDB backdrop" if tmdb_backdrop and poster_url == tmdb_backdrop
                    else "TMDB poster" if tmdb_poster and poster_url == tmdb_poster
                    else "IMDb" if imdb_poster and poster_url == imdb_poster
                    else "saved artwork" if poster_url
                    else "no artwork"
                )

                rating = first_value(imdb_details.get("rating"), tmdb_details.get("rating"), movie_doc.get("rating"))
                year = first_value(imdb_details.get("year"), tmdb_details.get("year"), movie_doc.get("year"))
                # Clear stale/guessed values when TMDB has no India streaming provider.
                ott = tmdb_details.get("ott_platform") or "N/A"
                imdb_id = first_value(imdb_details.get("imdb_id"), tmdb_details.get("imdb_id"))
                imdb_url = first_value(
                    imdb_details.get("url"),
                    movie_doc.get("imdb_url"),
                    f"https://www.imdb.com/title/{imdb_id}" if imdb_id else None,
                    tmdb_details.get("tmdb_url")
                )

                # If both sources returned no usable metadata, leave this movie
                # untouched rather than counting a no-op as a successful refresh.
                has_fresh_metadata = any((
                    has_value(imdb_details.get("title")),
                    has_value(imdb_details.get("genres")),
                    has_value(imdb_details.get("rating")),
                    has_value(imdb_details.get("runtime")),
                    has_value(imdb_details.get("year")),
                    has_value(tmdb_details.get("title")),
                    has_value(tmdb_details.get("genres")),
                    has_value(tmdb_details.get("rating")),
                    has_value(tmdb_details.get("runtime")),
                    has_value(tmdb_details.get("episode_run_time")),
                    has_value(tmdb_details.get("ott_platform")),
                    has_value(tmdb_details.get("languages")),
                    has_value(tmdb_details.get("poster_url")),
                    has_value(tmdb_details.get("backdrop_url")),
                    has_value(imdb_details.get("poster_url"))
                ))
                if not has_fresh_metadata:
                    failed += 1
                    logger.warning("No fresh IMDb/TMDB metadata found for %s; keeping saved data", base_name)
                    await save_refresh_checkpoint(base_name)
                    await asyncio.sleep(1)
                    continue

                updates = {
                    "title": title,
                    "genres": genres or movie_doc.get("genres") or "N/A",
                    "rating": rating if has_value(rating) else "N/A",
                    "runtime": runtime or old_runtime or "N/A",
                    "year": year,
                    "ott_platform": ott,
                    "online_languages": online_languages or movie_doc.get("online_languages") or "N/A",
                    "poster_url": poster_url,
                    "backup_poster_url": first_value(
                        *(url for url in (tmdb_poster, imdb_poster, movie_doc.get("backup_poster_url"))
                          if url and url != poster_url)
                    ),
                    "imdb_url": imdb_url or ""
                }
                await db.movie_updates.update_one(
                    {"_id": base_name},
                    {"$set": updates}
                )
                movie_doc.update(updates)
                updated += 1

                if refresh_stop_requested:
                    stopped = True
                    break

                # Existing announcements are edited in place. If no message ID
                # is saved, explicitly send a new announcement and verify that
                # Telegram's returned message ID was saved to MongoDB.
                if movie_doc.get("message_id"):
                    await update_movie_message(bot, base_name)
                else:
                    sent_message = await send_movie_update(bot, base_name)
                    if not sent_message:
                        post_failed += 1
                        logger.error(
                            "Refresh could not create channel announcement for %s",
                            base_name
                        )

                latest_doc = await db.movie_updates.find_one({"_id": base_name})
                if latest_doc and latest_doc.get("message_id"):
                    posted += 1
                elif not movie_doc.get("message_id") and sent_message is None:
                    pass
                else:
                    post_failed += 1
                    logger.error(
                        "No saved channel message ID after refresh for %s",
                        base_name
                    )

                await save_refresh_checkpoint(base_name)

                if refresh_stop_requested:
                    stopped = True
                    break
                await asyncio.sleep(1)
            except Exception:
                failed += 1
                logger.exception("Metadata refresh failed for %s", base_name)
                # Mark this item as attempted so a later resume continues
                # forward instead of getting stuck on one bad metadata record.
                if base_name:
                    await save_refresh_checkpoint(base_name)

        if refresh_stop_requested:
            stopped = True

        if not stopped:
            await refresh_state.update_one(
                {"_id": "metadata_refresh"},
                {"$set": {"last_id": None, "completed": True}},
                upsert=True
            )

        result_title = "⏹️ Refresh stopped." if stopped else "✅ Refresh complete!"
        await status.edit_text(
            f"<b>{result_title}\\n\\n"
            f"Movies checked: {checked}\\n"
            f"Metadata updated: {updated}\\n"
            f"Channel posts refreshed: {posted}\\n"
            f"Post creation/update failures: {post_failed}\\n"
            f"Metadata failures / no metadata: {failed}</b>"
        )
    finally:
        refresh_running = False
        refresh_stop_requested = False


@Client.on_message(filters.command("stoprefresh") & filters.user(ADMINS))
async def stop_refresh_all_movie_metadata(bot, message):
    global refresh_stop_requested

    if not refresh_running:
        await message.reply_text("<b>ℹ️ Abhi koi movie refresh nahi chal raha.</b>")
        return

    refresh_stop_requested = True
    await message.reply_text(
        "<b>⏹️ Stop request mil gayi. Current movie ka kaam complete hote hi refresh ruk jayega.</b>"
    )
