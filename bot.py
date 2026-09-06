import os
import time
import html
import urllib.parse

import telebot
import pycountry
import pytz

from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from pymongo import MongoClient
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from threading import Thread


# ============================================================
# RENDER KEEP-ALIVE SERVER
# ============================================================

app = Flask("")


@app.route("/")
def home():
    return "Bot is running and healthy!"


def run_web():
    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


def keep_alive():
    Thread(
        target=run_web,
        daemon=True
    ).start()


# ============================================================
# CONFIGURATION
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")
UPI_ID = os.getenv("UPI_ID")
CONTACT_USERNAME = os.getenv("CONTACT_USERNAME")


if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN environment variable is missing."
    )


if not MONGO_URI:
    raise ValueError(
        "MONGO_URI environment variable is missing."
    )


if not ADMIN_ID_RAW:
    raise ValueError(
        "ADMIN_ID environment variable is missing."
    )


if not UPI_ID:
    raise ValueError(
        "UPI_ID environment variable is missing."
    )


try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except Exception:
    raise ValueError(
        "ADMIN_ID must be a valid Telegram user ID."
    )


bot = telebot.TeleBot(
    BOT_TOKEN
)


# ============================================================
# TIMEZONE
# ============================================================

IST = ZoneInfo(
    "Asia/Kolkata"
)


# ============================================================
# COUNTRY TIMEZONES
# ============================================================

COUNTRY_BUTTONS = [

    ("🇮🇳 India", "Asia/Kolkata"),

    ("🇵🇰 Pakistan", "Asia/Karachi"),

    ("🇧🇩 Bangladesh", "Asia/Dhaka"),

    ("🇳🇵 Nepal", "Asia/Kathmandu"),

    ("🇱🇰 Sri Lanka", "Asia/Colombo"),

    ("🇦🇪 UAE", "Asia/Dubai"),

    ("🇸🇦 Saudi Arabia", "Asia/Riyadh"),

    ("🇸🇬 Singapore", "Asia/Singapore"),

    ("🇲🇾 Malaysia", "Asia/Kuala_Lumpur"),

    ("🇯🇵 Japan", "Asia/Tokyo"),

    ("🇰🇷 South Korea", "Asia/Seoul"),

    ("🇹🇭 Thailand", "Asia/Bangkok"),

    ("🇵🇭 Philippines", "Asia/Manila"),

    ("🇬🇧 United Kingdom", "Europe/London"),

    ("🇩🇪 Germany", "Europe/Berlin"),

    ("🇮🇹 Italy", "Europe/Rome"),

    ("🇿🇦 South Africa", "Africa/Johannesburg"),

    ("🇳🇬 Nigeria", "Africa/Lagos"),

    ("🇰🇪 Kenya", "Africa/Nairobi"),

    ("🇪🇬 Egypt", "Africa/Cairo"),

    ("🇹🇷 Turkey", "Europe/Istanbul")

]


# ============================================================
# MONGODB
# ============================================================

client = MongoClient(
    MONGO_URI
)

db = client[
    "sub_management"
]

channels_col = db[
    "channels"
]

users_col = db[
    "users"
]

profiles_col = db[
    "profiles"
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_plan(minutes):

    minutes = int(
        minutes
    )

    if minutes == 1:
        return "1 Minute"

    if minutes == 1440:
        return "1 Day"

    if minutes == 10080:
        return "7 Days"

    if minutes == 43200:
        return "30 Days"

    if minutes == 129600:
        return "90 Days"

    if minutes < 60:
        return f"{minutes} Minutes"

    if minutes % 1440 == 0:
        return f"{minutes // 1440} Days"

    if minutes % 60 == 0:
        return f"{minutes // 60} Hours"

    return f"{minutes} Minutes"


def format_remaining(seconds):

    if seconds <= 0:
        return "Expired"

    seconds = int(
        seconds
    )

    days = seconds // 86400

    hours = (
        seconds % 86400
    ) // 3600

    minutes = (
        seconds % 3600
    ) // 60

    secs = seconds % 60

    if days > 0:
        return (
            f"{days}d "
            f"{hours}h "
            f"{minutes}m"
        )

    if hours > 0:
        return (
            f"{hours}h "
            f"{minutes}m"
        )

    if minutes > 0:
        return (
            f"{minutes}m "
            f"{secs}s"
        )

    return f"{secs}s"


def get_user_timezone(user_id):

    profile = profiles_col.find_one(
        {
            "user_id": user_id
        },
        {
            "timezone": 1
        }
    )

    if profile:

        timezone_name = profile.get(
            "timezone"
        )

        if timezone_name:

            try:

                return ZoneInfo(
                    timezone_name
                )

            except Exception:
                pass

    return None


def format_user_time(
    timestamp,
    timezone
):

    if not timestamp:
        return "Unknown"

    try:

        return datetime.fromtimestamp(
            timestamp,
            timezone
        ).strftime(
            "%d %b %Y, %I:%M %p"
        )

    except Exception:
        return "Unknown"


def format_ist_time(
    timestamp
):

    if not timestamp:
        return "Unknown"

    try:

        return datetime.fromtimestamp(
            timestamp,
            IST
        ).strftime(
            "%d %b %Y, %I:%M %p"
        )

    except Exception:
        return "Unknown"


def get_contact_username():

    if not CONTACT_USERNAME:
        return "Admin"

    username = (
        CONTACT_USERNAME
        .strip()
    )

    if not username:
        return "Admin"

    if not username.startswith("@"):

        username = (
            "@"
            + username
        )

    return username


def get_contact_url():

    if not CONTACT_USERNAME:
        return None

    username = (
        CONTACT_USERNAME
        .strip()
        .lstrip("@")
    )

    if not username:
        return None

    return (
        f"https://t.me/"
        f"{username}"
    )


def safe_html(value):

    return html.escape(
        str(value or "")
    )


def send_admin_error(
    title,
    error
):

    try:

        bot.send_message(
            ADMIN_ID,
            (
                f"❌ <b>{safe_html(title)}</b>\n\n"
                f"<code>{safe_html(error)}</code>"
            ),
            parse_mode="HTML"
        )

    except Exception:
        pass


# ============================================================
# TIMEZONE SELECTOR
# ============================================================

def show_timezone_request(
    chat_id
):

    markup = InlineKeyboardMarkup()

    row = []

    for index, (
        country,
        timezone_name
    ) in enumerate(
        COUNTRY_BUTTONS
    ):

        row.append(
            InlineKeyboardButton(
                country,
                callback_data=(
                    f"tz_{index}"
                )
            )
        )

        if len(row) == 2:

            markup.row(
                *row
            )

            row = []

    if row:

        markup.row(
            *row
        )

    markup.add(
        InlineKeyboardButton(
            "✍️ Other Country",
            callback_data="tz_manual"
        )
    )

    bot.send_message(
        chat_id,
        "🌍 <b>Please select your country</b>",
        reply_markup=markup,
        parse_mode="HTML"
    )


def save_timezone(
    user_id,
    timezone_name,
    chat_id
):

    try:

        ZoneInfo(
            timezone_name
        )

    except Exception:

        return False

    profiles_col.update_one(

        {
            "user_id": user_id
        },

        {
            "$set": {

                "user_id":
                    user_id,

                "timezone":
                    timezone_name

            },

            "$unset": {

                "awaiting_country": "",

                "timezone_choices": ""

            }
        },

        upsert=True

    )

    # --------------------------------------------------------
    # OPEN PENDING CHANNEL
    # --------------------------------------------------------

    pending = users_col.find_one(
        {
            "user_id": user_id,

            "pending_channel_id": {
                "$exists": True
            }
        }
    )

    if pending:

        ch_id = pending.get(
            "pending_channel_id"
        )

        users_col.update_one(
            {
                "_id": pending["_id"]
            },
            {
                "$unset": {
                    "pending_channel_id": ""
                }
            }
        )

        if ch_id:

            send_channel_plans(
                chat_id,
                int(ch_id)
            )

    return True


def country_timezones(
    country_name
):

    aliases = {

        "india":
            "India",

        "pakistan":
            "Pakistan",

        "bangladesh":
            "Bangladesh",

        "nepal":
            "Nepal",

        "sri lanka":
            "Sri Lanka",

        "uae":
            "United Arab Emirates",

        "dubai":
            "United Arab Emirates",

        "saudi":
            "Saudi Arabia",

        "saudi arabia":
            "Saudi Arabia",

        "usa":
            "United States",

        "us":
            "United States",

        "united states":
            "United States",

        "uk":
            "United Kingdom",

        "england":
            "United Kingdom"

    }

    clean_name = " ".join(
        country_name
        .strip()
        .split()
    )

    clean_name = aliases.get(
        clean_name.lower(),
        clean_name
    )

    try:

        country = (
            pycountry
            .countries
            .search_fuzzy(
                clean_name
            )[0]
        )

        code = country.alpha_2

        return pytz.country_timezones.get(
            code,
            []
        )

    except Exception:

        return []


def timezone_choice_keyboard(
    choices
):

    markup = InlineKeyboardMarkup()

    for index, timezone_name in enumerate(
        choices
    ):

        readable = (
            timezone_name
            .split("/")[-1]
        )

        readable = readable.replace(
            "_",
            " "
        )

        markup.add(
            InlineKeyboardButton(
                f"🌍 {readable}",
                callback_data=(
                    f"tzpick_{index}"
                )
            )
        )

    return markup


# ============================================================
# SEND CHANNEL PLANS
# ============================================================

def send_channel_plans(
    chat_id,
    ch_id
):

    ch_data = channels_col.find_one(
        {
            "channel_id": ch_id
        }
    )

    if not ch_data:

        return False

    channel_name = safe_html(
        ch_data.get(
            "name",
            "Unknown Channel"
        )
    )

    markup = InlineKeyboardMarkup()

    plans = ch_data.get(
        "plans",
        {}
    )

    for p_time, p_price in plans.items():

        label = format_plan(
            int(p_time)
        )

        markup.add(

            InlineKeyboardButton(

                f"💳 {label} - ₹{p_price}",

                callback_data=(
                    f"select_{ch_id}_{p_time}"
                )

            )

        )

    contact_url = get_contact_url()

    if contact_url:

        markup.add(

            InlineKeyboardButton(

                "📞 Contact Admin",

                url=contact_url

            )

        )

    bot.send_message(

        chat_id,

        (
            f"You Are Joining "
            f"<b>{channel_name}</b>\n\n"

            "💎 Please Select Your "
            "Subscription Plan:"
        ),

        reply_markup=markup,

        parse_mode="HTML"

    )

    return True


# ============================================================
# START
# ============================================================

@bot.message_handler(
    commands=["start"]
)
def start_handler(
    message
):

    user_id = (
        message.from_user.id
    )

    text = (
        message.text or ""
    ).split()

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    if (
        user_id == ADMIN_ID
        and len(text) == 1
    ):

        bot.send_message(

            message.chat.id,

            "✅ <b>Admin Panel Active!</b>\n\n"

            "/add - Add/Edit Channel & Prices\n"
            "/channels - Manage Existing Channels\n"
            "/users - View Subscribers\n"
            "/timezone - Change Your Timezone",

            parse_mode="HTML"

        )

        return

    # --------------------------------------------------------
    # DEEP LINK
    # --------------------------------------------------------

    if len(text) > 1:

        try:

            ch_id = int(
                text[1]
            )

            ch_data = channels_col.find_one(
                {
                    "channel_id":
                        ch_id
                }
            )

            if not ch_data:
                return

            # ------------------------------------------------
            # SAVE USER BASIC INFO
            # ------------------------------------------------

            existing_user = users_col.find_one(
                {
                    "user_id":
                        user_id,

                    "channel_id":
                        ch_id
                }
            )

            if existing_user:

                users_col.update_one(

                    {
                        "_id":
                            existing_user["_id"]
                    },

                    {
                        "$set": {

                            "name":
                                message
                                .from_user
                                .first_name
                                or "",

                            "username":
                                message
                                .from_user
                                .username
                                or ""

                        }
                    }

                )

            else:

                users_col.insert_one(

                    {

                        "user_id":
                            user_id,

                        "channel_id":
                            ch_id,

                        "name":
                            message
                            .from_user
                            .first_name
                            or "",

                        "username":
                            message
                            .from_user
                            .username
                            or ""

                    }

                )

            # ------------------------------------------------
            # CHECK TIMEZONE
            # ------------------------------------------------

            timezone = get_user_timezone(
                user_id
            )

            if timezone is None:

                users_col.update_one(

                    {
                        "user_id":
                            user_id,

                        "channel_id":
                            ch_id

                    },

                    {
                        "$set": {

                            "pending_channel_id":
                                ch_id

                        }
                    }

                )

                show_timezone_request(
                    message.chat.id
                )

                return

            # ------------------------------------------------
            # SHOW PLANS
            # ------------------------------------------------

            send_channel_plans(

                message.chat.id,

                ch_id

            )

            return

        except Exception:
            pass

    # --------------------------------------------------------
    # NORMAL USER START
    # --------------------------------------------------------

    if user_id != ADMIN_ID:

        timezone = get_user_timezone(
            user_id
        )

        if timezone is None:

            show_timezone_request(
                message.chat.id
            )

        else:

            bot.send_message(

                message.chat.id,

                "Welcome!\n\n"
                "To join a channel, please use "
                "the link provided by the Admin."

            )


# ============================================================
# TIMEZONE COUNTRY CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        (
            call.data or ""
        ).startswith("tz_")
        and not (
            call.data or ""
        ).startswith("tzpick_")
)
def timezone_country_callback(
    call
):

    user_id = (
        call.from_user.id
    )

    try:

        if call.data == "tz_manual":

            profiles_col.update_one(

                {
                    "user_id":
                        user_id
                },

                {
                    "$set": {

                        "user_id":
                            user_id,

                        "awaiting_country":
                            True

                    }
                },

                upsert=True
            )

            bot.answer_callback_query(
                call.id
            )

            bot.send_message(

                call.message.chat.id,

                "✍️ Please type your country name.\n\n"
                "Example: India"

            )

            return

        index = int(
            call.data.split(
                "_"
            )[1]
        )

        if (
            index < 0
            or index >= len(
                COUNTRY_BUTTONS
            )
        ):

            raise ValueError(
                "Invalid timezone index."
            )

        country, timezone_name = (
            COUNTRY_BUTTONS[index]
        )

        if not save_timezone(
            user_id,
            timezone_name,
            call.message.chat.id
        ):

            raise ValueError(
                "Unable to save timezone."
            )

        bot.answer_callback_query(

            call.id,

            "✅ Timezone Saved!"

        )

        try:

            bot.delete_message(

                call.message.chat.id,

                call.message.message_id

            )

        except Exception:
            pass

    except Exception as e:

        try:

            bot.answer_callback_query(

                call.id,

                "❌ Timezone error!",

                show_alert=True

            )

        except Exception:
            pass

        send_admin_error(
            "Timezone Error",
            e
        )


# ============================================================
# MULTIPLE TIMEZONE CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        (
            call.data or ""
        ).startswith("tzpick_")
)
def timezone_multi_callback(
    call
):

    user_id = (
        call.from_user.id
    )

    try:

        index = int(
            call.data.split(
                "_"
            )[1]
        )

        profile = profiles_col.find_one(

            {
                "user_id":
                    user_id
            }

        )

        if not profile:

            bot.answer_callback_query(

                call.id,

                "❌ Please try again.",

                show_alert=True
            )

            return

        choices = profile.get(
            "timezone_choices",
            []
        )

        if (
            index < 0
            or index >= len(choices)
        ):

            bot.answer_callback_query(

                call.id,

                "❌ Invalid timezone.",

                show_alert=True

            )

            return

        timezone_name = choices[index]

        if not save_timezone(
            user_id,
            timezone_name,
            call.message.chat.id
        ):

            raise ValueError(
                "Unable to save timezone."
            )

        bot.answer_callback_query(

            call.id,

            "✅ Timezone Saved!"

        )

        try:

            bot.delete_message(

                call.message.chat.id,

                call.message.message_id

            )

        except Exception:
            pass

    except Exception as e:

        try:

            bot.answer_callback_query(

                call.id,

                "❌ Timezone error!",

                show_alert=True

            )

        except Exception:
            pass

        send_admin_error(
            "Timezone Error",
            e
        )


# ============================================================
# MANUAL COUNTRY INPUT
# ============================================================

def waiting_for_country(
    message
):

    profile = profiles_col.find_one(

        {
            "user_id":
                message.from_user.id,

            "awaiting_country":
                True
        }

    )

    return bool(
        profile
    )


@bot.message_handler(
    content_types=["text"],
    func=waiting_for_country
)
def manual_country_handler(
    message
):

    if (
        message.text or ""
    ).startswith("/"):
        return

    user_id = (
        message.from_user.id
    )

    country_name = (
        message.text or ""
    ).strip()

    zones = country_timezones(
        country_name
    )

    if not zones:

        bot.send_message(

            message.chat.id,

            "❌ Country not found.\n\n"
            "Please enter a valid country name."

        )

        return

    # --------------------------------------------------------
    # ONE TIMEZONE
    # --------------------------------------------------------

    if len(zones) == 1:

        timezone_name = zones[0]

        if save_timezone(

            user_id,

            timezone_name,

            message.chat.id

        ):

            bot.send_message(

                message.chat.id,

                "✅ Timezone Saved!"

            )

        else:

            bot.send_message(

                message.chat.id,

                "❌ Unable to save timezone."

            )

        return

    # --------------------------------------------------------
    # MULTIPLE TIMEZONES
    # --------------------------------------------------------

    profiles_col.update_one(

        {
            "user_id":
                user_id
        },

        {
            "$set": {

                "timezone_choices":
                    zones

            },

            "$unset": {

                "awaiting_country":
                    ""

            }
        },

        upsert=True
    )

    markup = timezone_choice_keyboard(
        zones
    )

    bot.send_message(

        message.chat.id,

        "🌍 This country has multiple timezones.\n\n"
        "Please select your timezone:",

        reply_markup=markup

    )


# ============================================================
# /TIMEZONE
# ============================================================

@bot.message_handler(
    commands=["timezone"]
)
def timezone_command(
    message
):

    show_timezone_request(
        message.chat.id
    )


# ============================================================
# CHANNELS
# ============================================================

@bot.message_handler(
    commands=["channels"],
    func=lambda m:
        m.from_user.id == ADMIN_ID
)
def list_channels(
    message
):

    markup = InlineKeyboardMarkup()

    cursor = channels_col.find(
        {
            "admin_id":
                ADMIN_ID
        }
    )

    count = 0

    for ch in cursor:

        channel_name = safe_html(
            ch.get(
                "name",
                "Unknown"
            )
        )

        markup.add(

            InlineKeyboardButton(

                f"Channel: {ch['name']}",

                callback_data=(
                    f"manage_{ch['channel_id']}"
                )

            )

        )

        count += 1

    markup.add(

        InlineKeyboardButton(

            "➕ Add New Channel",

            callback_data="add_new"

        )

    )

    if count == 0:

        bot.send_message(

            ADMIN_ID,

            "No channels found.\n\n"
            "Click below to add one.",

            reply_markup=markup

        )

    else:

        bot.send_message(

            ADMIN_ID,

            "Your Managed Channels:",

            reply_markup=markup

        )


# ============================================================
# ADD CHANNEL
# ============================================================

@bot.message_handler(
    commands=["add"],
    func=lambda m:
        m.from_user.id == ADMIN_ID
)
def add_channel_start(
    message
):

    msg = bot.send_message(

        ADMIN_ID,

        "Please ensure the bot is an Admin in your channel,\n"
        "then FORWARD any message from that channel here."

    )

    bot.register_next_step_handler(
        msg,
        get_plans
    )


# ============================================================
# ADD NEW CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data == "add_new"
)
def cb_add_new(
    call
):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(

            call.id,

            "⛔ Only Owner can add channels!",

            show_alert=True

        )

        return

    bot.answer_callback_query(
        call.id
    )

    msg = bot.send_message(

        ADMIN_ID,

        "Please FORWARD any message from your channel here."

    )

    bot.register_next_step_handler(
        msg,
        get_plans
    )


# ============================================================
# GET CHANNEL
# ============================================================

def get_plans(
    message
):

    if message.from_user.id != ADMIN_ID:
        return

    if message.forward_from_chat:

        ch_id = (
            message
            .forward_from_chat
            .id
        )

        ch_name = (
            message
            .forward_from_chat
            .title
        )

        msg = bot.send_message(

            ADMIN_ID,

            f"Channel Detected: "
            f"<b>{safe_html(ch_name)}</b>\n\n"

            "Enter plans in format:\n"
            "<code>Minutes:Price, Minutes:Price</code>\n\n"

            "Example:\n"
            "<code>1:10, 1440:99, "
            "10080:199, 43200:399, "
            "129600:799</code>\n\n"

            "This means:\n"
            "1 Minute\n"
            "1 Day\n"
            "7 Days\n"
            "30 Days\n"
            "90 Days",

            parse_mode="HTML"

        )

        bot.register_next_step_handler(

            msg,

            finalize_channel,

            ch_id,

            ch_name

        )

    else:

        bot.send_message(

            ADMIN_ID,

            "❌ Error: Message was not forwarded.\n\n"
            "Use /add to try again."

        )


# ============================================================
# SAVE CHANNEL PLANS
# ============================================================

def finalize_channel(
    message,
    ch_id,
    ch_name
):

    if message.from_user.id != ADMIN_ID:
        return

    try:

        raw_plans = (
            message.text or ""
        ).split(",")

        plans_dict = {}

        for p in raw_plans:

            parts = p.strip().split(":")

            if len(parts) != 2:
                raise ValueError(
                    "Invalid plan format."
                )

            t = str(
                int(
                    parts[0].strip()
                )
            )

            pr = (
                parts[1].strip()
            )

            if not pr:
                raise ValueError(
                    "Price is empty."
                )

            plans_dict[t] = pr

        if not plans_dict:

            raise ValueError(
                "No plans found."
            )

        channels_col.update_one(

            {
                "channel_id":
                    ch_id
            },

            {
                "$set": {

                    "name":
                        ch_name,

                    "plans":
                        plans_dict,

                    "admin_id":
                        ADMIN_ID

                }
            },

            upsert=True

        )

        bot_username = (
            bot.get_me().username
        )

        bot.send_message(

            ADMIN_ID,

            "✅ <b>Setup Successful!</b>\n\n"

            "Invite Link for users:\n"

            f"<code>https://t.me/"
            f"{safe_html(bot_username)}"
            f"?start={ch_id}</code>",

            parse_mode="HTML"

        )

    except Exception:

        bot.send_message(

            ADMIN_ID,

            "❌ Invalid format.\n\n"

            "Use:\n"

            "<code>1:10, 1440:99, "
            "10080:199, 43200:399, "
            "129600:799</code>",

            parse_mode="HTML"

        )


# ============================================================
# USER SELECTS PLAN
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        (
            call.data or ""
        ).startswith("select_")
)
def user_pays(
    call
):

    try:

        parts = (
            call.data or ""
        ).split("_")

        if len(parts) != 3:

            bot.answer_callback_query(

                call.id,

                "❌ Invalid plan.",

                show_alert=True

            )

            return

        _, ch_id, mins = parts

        ch_id = int(
            ch_id
        )

        mins = int(
            mins
        )

        ch_data = channels_col.find_one(

            {
                "channel_id":
                    ch_id
            }
        )

        if not ch_data:

            bot.answer_callback_query(

                call.id,

                "❌ Channel not found!",

                show_alert=True

            )

            return

        plans = ch_data.get(
            "plans",
            {}
        )

        if str(mins) not in plans:

            bot.answer_callback_query(

                call.id,

                "❌ Plan not found!",

                show_alert=True

            )

            return

        price = plans[
            str(mins)
        ]

        plan_name = format_plan(
            mins
        )

        # ----------------------------------------------------
        # UPI QR
        # ----------------------------------------------------

        qr_data = (

            f"upi://pay"
            f"?pa={UPI_ID}"
            f"&am={price}"
            f"&cu=INR"

        )

        qr_url = (

            "https://api.qrserver.com/"
            "v1/create-qr-code/"
            "?size=300x300&data="

            + urllib.parse.quote(
                qr_data,
                safe=""
            )

        )

        # ----------------------------------------------------
        # PAYMENT BUTTONS
        # ----------------------------------------------------

        markup = InlineKeyboardMarkup()

        markup.add(

            InlineKeyboardButton(

                "✅ I Have Paid",

                callback_data=(
                    f"paid_{ch_id}_{mins}"
                )

            )

        )

        contact_url = get_contact_url()

        if contact_url:

            markup.add(

                InlineKeyboardButton(

                    "📞 Contact Admin",

                    url=contact_url

                )

            )

        # ----------------------------------------------------
        # PAYMENT SCREEN
        # ----------------------------------------------------

        caption = (

            f"📦 <b>Plan:</b> "
            f"{safe_html(plan_name)}\n"

            f"💰 <b>Price:</b> "
            f"₹{safe_html(price)}\n\n"

            f"UPI ID: "
            f"<code>{safe_html(UPI_ID)}</code>\n\n"

            "Please complete the payment and click "
            "<b>I Have Paid</b>.\n\n"

            f"Admin: "
            f"{safe_html(get_contact_username())}"

        )

        bot.send_photo(

            call.message.chat.id,

            qr_url,

            caption=caption,

            reply_markup=markup,

            parse_mode="HTML"

        )

        bot.answer_callback_query(
            call.id
        )

    except Exception as e:

        try:

            bot.answer_callback_query(

                call.id,

                "❌ Something went wrong!",

                show_alert=True

            )

        except Exception:
            pass

        send_admin_error(
            "Payment Flow Error",
            e
        )


# ============================================================
# USER PRESSES I HAVE PAID
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        (
            call.data or ""
        ).startswith("paid_")
)
def admin_notify(
    call
):

    try:

        parts = (
            call.data or ""
        ).split("_")

        if len(parts) != 3:

            bot.answer_callback_query(

                call.id,

                "❌ Invalid payment request.",

                show_alert=True

            )

            return

        _, ch_id, mins = parts

        ch_id = int(
            ch_id
        )

        mins = int(
            mins
        )

        user = call.from_user

        ch_data = channels_col.find_one(

            {
                "channel_id":
                    ch_id
            }
        )

        if not ch_data:

            bot.answer_callback_query(

                call.id,

                "❌ Channel not found!",

                show_alert=True

            )

            return

        plans = ch_data.get(
            "plans",
            {}
        )

        if str(mins) not in plans:

            bot.answer_callback_query(

                call.id,

                "❌ Plan not found!",

                show_alert=True

            )

            return

        price = plans[
            str(mins)
        ]

        plan_name = format_plan(
            mins
        )

        # ----------------------------------------------------
        # SAVE PAYMENT REQUEST
        # ----------------------------------------------------

        users_col.update_one(

            {
                "user_id":
                    user.id,

                "channel_id":
                    ch_id
            },

            {
                "$set": {

                    "user_id":
                        user.id,

                    "channel_id":
                        ch_id,

                    "name":
                        user.first_name
                        or "",

                    "username":
                        user.username
                        or "",

                    "plan_minutes":
                        mins,

                    "status":
                        "payment_pending",

                    "requested_at":
                        time.time()

                },

                "$unset": {

                    "joined_at":
                        "",

                    "expiry":
                        "",

                    "invite_link":
                        "",

                    "invite_link_expires_at":
                        "",

                    "approved_at":
                        ""

                }

            },

            upsert=True

        )

        # ----------------------------------------------------
        # ADMIN BUTTONS
        # ----------------------------------------------------

        markup = InlineKeyboardMarkup()

        markup.add(

            InlineKeyboardButton(

                "✅ Approve",

                callback_data=(
                    f"app_{user.id}_"
                    f"{ch_id}_{mins}"
                )

            ),

            InlineKeyboardButton(

                "❌ Reject",

                callback_data=(
                    f"rej_{user.id}_{ch_id}"
                )

            )

        )

        # ----------------------------------------------------
        # ADMIN NOTIFICATION
        # ----------------------------------------------------

        admin_text = (

            "🔔 <b>Payment Verification Required!</b>\n\n"

            f"👤 User: "
            f"{safe_html(user.first_name)}\n"

            f"🆔 User ID: "
            f"<code>{user.id}</code>\n"

            f"📢 Channel: "
            f"{safe_html(ch_data.get('name', 'Unknown'))}\n"

            f"📦 Plan: "
            f"{safe_html(plan_name)}\n"

            f"💰 Price: "
            f"₹{safe_html(price)}"

        )

        bot.send_message(

            ADMIN_ID,

            admin_text,

            reply_markup=markup,

            parse_mode="HTML"

        )

        # ----------------------------------------------------
        # USER CONFIRMATION
        # ----------------------------------------------------

        user_markup = InlineKeyboardMarkup()

        contact_url = get_contact_url()

        if contact_url:

            user_markup.add(

                InlineKeyboardButton(

                    "📞 Contact Admin",

                    url=contact_url

                )

            )

        bot.send_message(

            call.message.chat.id,

            "✅ <b>Your payment request has been sent.</b>\n\n"
            "Please wait for Admin approval.\n\n"

            f"Admin: "
            f"{safe_html(get_contact_username())}",

            reply_markup=user_markup,

            parse_mode="HTML"

        )

        bot.answer_callback_query(

            call.id,

            "✅ Request sent!"

        )

    except Exception as e:

        try:

            bot.answer_callback_query(

                call.id,

                "❌ Error!",

                show_alert=True

            )

        except Exception:
            pass

        send_admin_error(
            "Payment Request Error",
            e
        )


# ============================================================
# APPROVE PAYMENT
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        (
            call.data or ""
        ).startswith("app_")
)
def approve_now(
    call
):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(

            call.id,

            "⛔ Only Owner can approve payments!",

            show_alert=True

        )

        return

    try:

        parts = (
            call.data or ""
        ).split("_")

        if len(parts) != 4:

            raise ValueError(
                "Invalid approval data."
            )

        _, u_id, ch_id, mins = parts

        u_id = int(
            u_id
        )

        ch_id = int(
            ch_id
        )

        mins = int(
            mins
        )

        subscription = users_col.find_one(

            {
                "user_id":
                    u_id,

                "channel_id":
                    ch_id,

                "status":
                    "payment_pending"

            }

        )

        if not subscription:

            bot.answer_callback_query(

                call.id,

                "❌ User request not found!",

                show_alert=True

            )

            return

        ch_data = channels_col.find_one(

            {
                "channel_id":
                    ch_id
            }

        )

        if not ch_data:

            raise ValueError(
                "Channel not found."
            )

        plans = ch_data.get(
            "plans",
            {}
        )

        if str(mins) not in plans:

            raise ValueError(
                "Plan no longer exists."
            )

        plan_name = format_plan(
            mins
        )

        # ----------------------------------------------------
        # UNBAN OLD EXPIRED USER
        #
        # Safe because only_if_banned=True.
        # ----------------------------------------------------

        try:

            bot.unban_chat_member(

                ch_id,

                u_id,

                only_if_banned=True

            )

        except Exception:

            pass

        # ----------------------------------------------------
        # REVOKE OLD INVITE IF EXISTS
        # ----------------------------------------------------

        old_invite = subscription.get(
            "invite_link"
        )

        if old_invite:

            try:

                bot.revoke_chat_invite_link(

                    ch_id,

                    old_invite

                )

            except Exception:

                pass

        # ----------------------------------------------------
        # WAITING STATE
        # ----------------------------------------------------

        users_col.update_one(

            {
                "_id":
                    subscription["_id"]
            },

            {
                "$set": {

                    "plan_minutes":
                        mins,

                    "status":
                        "waiting",

                    "approved_at":
                        time.time()

                },

                "$unset": {

                    "joined_at":
                        "",

                    "expiry":
                        "",

                    "invite_link":
                        "",

                    "invite_link_expires_at":
                        ""

                }

            }

        )

        # ----------------------------------------------------
        # TEMPORARY ONE-PERSON INVITE
        # ----------------------------------------------------

        now_timestamp = int(
            time.time()
        )

        invite_expiry_timestamp = (

            now_timestamp
            + (
                mins * 60
            )

        )

        invite_expiry_datetime = (
            datetime.fromtimestamp(
                invite_expiry_timestamp,
                ZoneInfo("UTC")
            )
        )

        link = bot.create_chat_invite_link(

            ch_id,

            member_limit=1,

            expire_date=(
                invite_expiry_datetime
            )

        )

        users_col.update_one(

            {
                "_id":
                    subscription["_id"]
            },

            {
                "$set": {

                    "invite_link":
                        link.invite_link,

                    "invite_link_expires_at":
                        invite_expiry_timestamp

                }

            }

        )

        # ----------------------------------------------------
        # SEND LINK TO USER
        # ----------------------------------------------------

        bot.send_message(

            u_id,

            "🥳 <b>Payment Approved!</b>\n\n"

            f"📦 Subscription: "
            f"<b>{safe_html(plan_name)}</b>\n\n"

            "🔗 Join Channel:\n"
            f"{safe_html(link.invite_link)}\n\n"

            "⚠️ Your subscription timer will start "
            "<b>when you join the channel</b>.",

            parse_mode="HTML"

        )

        # ----------------------------------------------------
        # UPDATE ADMIN MESSAGE
        # ----------------------------------------------------

        try:

            bot.edit_message_text(

                "✅ <b>Payment Approved!</b>\n\n"

                f"👤 User ID: "
                f"<code>{u_id}</code>\n"

                f"📦 Plan: "
                f"<code>{safe_html(plan_name)}</code>\n\n"

                "⏳ Waiting for user to join...\n"
                "Timer has NOT started yet.",

                call.message.chat.id,

                call.message.message_id,

                parse_mode="HTML"

            )

        except Exception:

            pass

        bot.answer_callback_query(

            call.id,

            "✅ Payment approved!"

        )

    except Exception as e:

        try:

            bot.answer_callback_query(

                call.id,

                "❌ Approval error!",

                show_alert=True

            )

        except Exception:
            pass

        send_admin_error(
            "Approval Error",
            e
        )


# ============================================================
# REJECT PAYMENT
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        (
            call.data or ""
        ).startswith("rej_")
)
def reject_payment(
    call
):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(

            call.id,

            "⛔ Only Owner can reject payments!",

            show_alert=True

        )

        return

    try:

        parts = (
            call.data or ""
        ).split("_")

        if len(parts) != 3:

            raise ValueError(
                "Invalid reject data."
            )

        _, u_id, ch_id = parts

        u_id = int(
            u_id
        )

        ch_id = int(
            ch_id
        )

        users_col.delete_one(

            {
                "user_id":
                    u_id,

                "channel_id":
                    ch_id,

                "status":
                    "payment_pending"

            }

        )

        bot.answer_callback_query(

            call.id,

            "❌ Payment rejected!"

        )

        bot.send_message(

            u_id,

            "❌ <b>Payment Request Rejected!</b>\n\n"

            "Please complete the payment and then "
            "click <b>I Have Paid</b>.",

            parse_mode="HTML"

        )

        bot.send_message(

            ADMIN_ID,

            "❌ <b>Request Rejected!</b>\n\n"

            f"User ID: <code>{u_id}</code>\n\n"

            "The user has been notified.",

            parse_mode="HTML"

        )

        try:

            bot.edit_message_text(

                "❌ <b>Payment Rejected!</b>\n\n"

                f"User ID: <code>{u_id}</code>",

                call.message.chat.id,

                call.message.message_id,

                parse_mode="HTML"

            )

        except Exception:

            pass

    except Exception as e:

        try:

            bot.answer_callback_query(

                call.id,

                "❌ Rejection error!",

                show_alert=True

            )

        except Exception:
            pass

        send_admin_error(
            "Rejection Error",
            e
        )


# ============================================================
# TRACK ACTUAL CHANNEL JOIN
# ============================================================

@bot.chat_member_handler()
def track_channel_join(
    update
):

    try:

        new_status = (
            update
            .new_chat_member
            .status
        )

        old_status = (
            update
            .old_chat_member
            .status
        )

        user = (
            update
            .new_chat_member
            .user
        )

        ch_id = (
            update
            .chat
            .id
        )

        joined_statuses = [

            "member",

            "administrator"

        ]

        # ----------------------------------------------------
        # ALREADY A MEMBER BEFORE
        # ----------------------------------------------------

        if (

            new_status
            in joined_statuses

            and old_status
            in joined_statuses

        ):

            return

        # ----------------------------------------------------
        # NOT A JOIN
        # ----------------------------------------------------

        if new_status not in joined_statuses:

            return

        # ----------------------------------------------------
        # FIND WAITING SUBSCRIPTION
        # ----------------------------------------------------

        subscription = users_col.find_one(

            {
                "user_id":
                    user.id,

                "channel_id":
                    ch_id,

                "status":
                    "waiting"

            }

        )

        if not subscription:

            return

        # ----------------------------------------------------
        # TIMER STARTS HERE
        # ----------------------------------------------------

        joined_timestamp = time.time()

        plan_minutes = int(

            subscription.get(
                "plan_minutes",
                0
            )

        )

        if plan_minutes <= 0:

            return

        expiry_timestamp = (

            joined_timestamp

            + (
                plan_minutes * 60
            )

        )

        users_col.update_one(

            {
                "_id":
                    subscription["_id"]
            },

            {
                "$set": {

                    "joined_at":
                        joined_timestamp,

                    "expiry":
                        expiry_timestamp,

                    "status":
                        "active",

                    "name":
                        user.first_name
                        or "",

                    "username":
                        user.username
                        or ""

                }

            }

        )

        plan_name = format_plan(
            plan_minutes
        )

        # ----------------------------------------------------
        # ADMIN TIME = IST
        # ----------------------------------------------------

        admin_joined_text = format_ist_time(

            joined_timestamp

        )

        admin_expiry_text = format_ist_time(

            expiry_timestamp

        )

        # ----------------------------------------------------
        # USER TIMEZONE
        # ----------------------------------------------------

        user_timezone = get_user_timezone(
            user.id
        )

        if user_timezone is None:

            user_timezone = IST

        user_joined_text = format_user_time(

            joined_timestamp,

            user_timezone

        )

        user_expiry_text = format_user_time(

            expiry_timestamp,

            user_timezone

        )

        timezone_name = str(

            getattr(

                user_timezone,

                "key",

                "Asia/Kolkata"

            )

        )

        # ----------------------------------------------------
        # OWNER NOTIFICATION
        # ----------------------------------------------------

        bot.send_message(

            ADMIN_ID,

            "👤 <b>User Joined!</b>\n\n"

            f"User: "
            f"{safe_html(user.first_name)}\n"

            f"User ID: "
            f"<code>{user.id}</code>\n"

            f"Channel ID: "
            f"<code>{ch_id}</code>\n\n"

            "📥 Joined:\n"

            f"{safe_html(admin_joined_text)} IST\n\n"

            "📦 Subscription:\n"

            f"{safe_html(plan_name)}\n\n"

            "🔴 Expires:\n"

            f"{safe_html(admin_expiry_text)} IST",

            parse_mode="HTML"

        )

        # ----------------------------------------------------
        # USER NOTIFICATION
        # ----------------------------------------------------

        bot.send_message(

            user.id,

            "✅ <b>Subscription Started!</b>\n\n"

            "Your subscription has started now.\n\n"

            f"📦 Duration: "
            f"<b>{safe_html(plan_name)}</b>\n\n"

            "📥 Joined:\n"

            f"{safe_html(user_joined_text)}\n\n"

            "🔴 Expires at:\n"

            f"{safe_html(user_expiry_text)}\n\n"

            f"🌍 Timezone: "
            f"<code>{safe_html(timezone_name)}</code>",

            parse_mode="HTML"

        )

    except Exception as e:

        send_admin_error(
            "Join Tracking Error",
            e
        )


# ============================================================
# /USERS
# ============================================================

@bot.message_handler(
    commands=["users"],
    func=lambda m:
        m.from_user.id == ADMIN_ID
)
def show_users(
    message
):

    try:

        users = list(

            users_col.find(

                {
                    "channel_id": {
                        "$exists":
                            True
                    }
                }

            )

        )

        now = time.time()

        blocks = []

        for user in users:

            status = user.get(
                "status",
                "unknown"
            )

            # Ignore payment requests
            if status == "payment_pending":
                continue

            user_id = user.get(
                "user_id",
                "Unknown"
            )

            channel_id = user.get(
                "channel_id",
                "Unknown"
            )

            name = safe_html(
                user.get(
                    "name",
                    "Unknown"
                )
            )

            # ------------------------------------------------
            # WAITING
            # ------------------------------------------------

            if status == "waiting":

                block = (

                    f"👤 <b>{name}</b>\n"

                    f"🆔 ID: "
                    f"<code>{user_id}</code>\n"

                    f"📢 Channel: "
                    f"<code>{channel_id}</code>\n"

                    "🟡 Status: Waiting to join\n"

                    "⏳ Timer: Not started yet"

                )

                blocks.append(
                    block
                )

                continue

            # ------------------------------------------------
            # ACTIVE
            # ------------------------------------------------

            if status == "active":

                joined_ts = user.get(
                    "joined_at"
                )

                expiry_ts = user.get(
                    "expiry"
                )

                joined_text = format_ist_time(
                    joined_ts
                )

                expiry_text = format_ist_time(
                    expiry_ts
                )

                if expiry_ts:

                    remaining = (
                        format_remaining(
                            int(
                                expiry_ts - now
                            )
                        )
                    )

                else:

                    remaining = "Unknown"

                block = (

                    f"👤 <b>{name}</b>\n"

                    f"🆔 ID: "
                    f"<code>{user_id}</code>\n"

                    f"📢 Channel: "
                    f"<code>{channel_id}</code>\n"

                    "🟢 Status: Active\n"

                    f"📥 Joined: "
                    f"{safe_html(joined_text)} IST\n"

                    f"🔴 Expires: "
                    f"{safe_html(expiry_text)} IST\n"

                    f"⏳ Remaining: "
                    f"{safe_html(remaining)}"

                )

                blocks.append(
                    block
                )

                continue

            # ------------------------------------------------
            # OTHER
            # ------------------------------------------------

            block = (

                f"👤 <b>{name}</b>\n"

                f"🆔 ID: "
                f"<code>{user_id}</code>\n"

                f"📢 Channel: "
                f"<code>{channel_id}</code>\n"

                f"Status: "
                f"<code>{safe_html(status)}</code>"

            )

            blocks.append(
                block
            )

        if not blocks:

            bot.send_message(

                ADMIN_ID,

                "👥 <b>Subscribers</b>\n\n"
                "No active/waiting subscribers.",

                parse_mode="HTML"

            )

            return

        header = (
            "👥 <b>SUBSCRIBERS</b>\n\n"
        )

        chunks = []

        current = header

        for block in blocks:

            addition = (
                block
                + "\n\n"
            )

            if (
                len(current)
                + len(addition)
                > 3900
            ):

                chunks.append(
                    current
                )

                current = (
                    "👥 <b>SUBSCRIBERS</b>\n\n"
                    + addition
                )

            else:

                current += addition

        if current.strip():

            chunks.append(
                current
            )

        for chunk in chunks:

            bot.send_message(

                ADMIN_ID,

                chunk,

                parse_mode="HTML"

            )

    except Exception as e:

        print(
            "Users command error:",
            e
        )

        try:

            bot.send_message(

                ADMIN_ID,

                "❌ Unable to load subscribers.\n\n"
                "Please try /users again."

            )

        except Exception:
            pass


# ============================================================
# MANAGE CHANNEL
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        (
            call.data or ""
        ).startswith("manage_")
)
def manage_ch(
    call
):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(

            call.id,

            "⛔ Only Owner can manage channels!",

            show_alert=True

        )

        return

    try:

        ch_id = int(

            (
                call.data or ""
            ).split("_")[1]

        )

        ch_data = channels_col.find_one(

            {
                "channel_id":
                    ch_id
            }

        )

        if not ch_data:

            bot.answer_callback_query(

                call.id,

                "❌ Channel not found!",

                show_alert=True

            )

            return

        bot_username = (
            bot.get_me().username
        )

        link = (

            f"https://t.me/"
            f"{bot_username}"
            f"?start={ch_id}"

        )

        bot.edit_message_text(

            "⚙️ Settings for: "
            f"<b>{safe_html(ch_data.get('name', 'Unknown'))}</b>\n\n"

            "Your Link:\n"

            f"<code>{safe_html(link)}</code>\n\n"

            "To edit prices, use /add and "
            "forward a message from this channel again.",

            call.message.chat.id,

            call.message.message_id,

            parse_mode="HTML"

        )

        bot.answer_callback_query(
            call.id
        )

    except Exception as e:

        try:

            bot.answer_callback_query(

                call.id,

                "❌ Error!",

                show_alert=True

            )

        except Exception:
            pass

        send_admin_error(
            "Manage Channel Error",
            e
        )


# ============================================================
# AUTOMATICALLY HANDLE EXPIRED USERS
# ============================================================

def kick_expired_users():

    now = time.time()

    expired_users = users_col.find(

        {
            "status":
                "active",

            "expiry": {
                "$lte":
                    now
            }
        }

    )

    try:

        bot_username = (
            bot.get_me().username
        )

    except Exception:

        bot_username = ""

    for user in expired_users:

        try:

            user_id = user.get(
                "user_id"
            )

            channel_id = user.get(
                "channel_id"
            )

            if not user_id or not channel_id:

                continue

            # ------------------------------------------------
            # REVOKE CHANNEL ACCESS
            #
            # For a Telegram CHANNEL, ban_chat_member is the
            # method that actually removes the member.
            # The user stays banned until renewal approval.
            # ------------------------------------------------

            access_removed = False

            try:

                bot.ban_chat_member(

                    channel_id,

                    user_id

                )

                access_removed = True

            except Exception as ban_error:

                print(
                    "Ban expired user error:",
                    ban_error
                )

                # ------------------------------------------------
                # Fallback for supergroups
                # ------------------------------------------------

                try:

                    bot.restrict_chat_member(

                        channel_id,

                        user_id,

                        permissions=(
                            telebot.types
                            .ChatPermissions(
                                can_send_messages=False,

                                can_send_audios=False,

                                can_send_documents=False,

                                can_send_photos=False,

                                can_send_videos=False,

                                can_send_video_notes=False,

                                can_send_voice_notes=False,

                                can_send_polls=False,

                                can_send_other_messages=False,

                                can_add_web_page_previews=False,

                                can_invite_users=False,

                                can_pin_messages=False

                            )
                        )

                    )

                    access_removed = True

                except Exception as restrict_error:

                    print(
                        "Restriction fallback error:",
                        restrict_error
                    )

            # ------------------------------------------------
            # REVOKE OLD INVITE
            # ------------------------------------------------

            old_invite = user.get(
                "invite_link"
            )

            if old_invite:

                try:

                    bot.revoke_chat_invite_link(

                        channel_id,

                        old_invite

                    )

                except Exception:
                    pass

            # ------------------------------------------------
            # PERMANENT BOT RENEW LINK
            # ------------------------------------------------

            rejoin_url = (

                f"https://t.me/"
                f"{bot_username}"
                f"?start={channel_id}"

            )

            markup = InlineKeyboardMarkup()

            markup.add(

                InlineKeyboardButton(

                    "🔄 Re-join / Renew",

                    url=rejoin_url

                )

            )

            # ------------------------------------------------
            # USER MESSAGE
            # ------------------------------------------------

            try:

                bot.send_message(

                    user_id,

                    "⏰ <b>Subscription Expired!</b>\n\n"

                    "Your premium subscription has expired.\n\n"

                    "Click below to renew:",

                    reply_markup=markup,

                    parse_mode="HTML"

                )

            except Exception as message_error:

                print(
                    "Expiry user message error:",
                    message_error
                )

            # ------------------------------------------------
            # REMOVE OLD SUBSCRIPTION RECORD
            #
            # New renewal creates a fresh record.
            # ------------------------------------------------

            users_col.delete_one(

                {
                    "_id":
                        user["_id"]
                }

            )

            print(
                f"Expired subscription handled: "
                f"user={user_id}, "
                f"channel={channel_id}, "
                f"access_removed={access_removed}"
            )

        except Exception as e:

            print(
                "Expiry error:",
                e
            )

            send_admin_error(
                "Expiry Error",
                e
            )


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":

    keep_alive()

    scheduler = BackgroundScheduler()

    scheduler.add_job(

        kick_expired_users,

        "interval",

        minutes=1,

        id="subscription_expiry_checker",

        replace_existing=True

    )

    scheduler.start()

    bot.remove_webhook()

    print(
        "Bot is running..."
    )

    bot.infinity_polling(

        timeout=20,

        long_polling_timeout=10,

        allowed_updates=[

            "message",

            "callback_query",

            "chat_member"

        ]

    )