import os
import re
import telebot

from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)

from pymongo import MongoClient

from datetime import datetime, timedelta

from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from flask import Flask

from threading import Thread

import pytz
import pycountry


# ============================================================
# FLASK KEEP ALIVE
# ============================================================

app = Flask("")


@app.route("/")
def home():
    return "Bot is running and healthy!"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port
    )


def keep_alive():
    thread = Thread(
        target=run_web
    )
    thread.daemon = True
    thread.start()


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
UPI_ID = os.environ.get("UPI_ID")
CONTACT_USERNAME = os.environ.get(
    "CONTACT_USERNAME",
    "Its_Lozo"
)


# ============================================================
# BOT
# ============================================================

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


# ============================================================
# COUNTRY / TIMEZONE DATA
# ============================================================

# Common country buttons
COUNTRY_BUTTONS = {
    "🇮🇳 India": "IN",
    "🇺🇸 USA": "US",
    "🇬🇧 UK": "GB",
    "🇦🇪 UAE": "AE",
    "🇸🇦 Saudi Arabia": "SA",
    "🇵🇰 Pakistan": "PK",
    "🇧🇩 Bangladesh": "BD",
    "🇳🇵 Nepal": "NP",
    "🇱🇰 Sri Lanka": "LK",
    "🇦🇺 Australia": "AU",
    "🇨🇦 Canada": "CA",
    "🇩🇪 Germany": "DE",
    "🇫🇷 France": "FR",
    "🇮🇹 Italy": "IT",
    "🇪🇸 Spain": "ES",
    "🇯🇵 Japan": "JP",
    "🇰🇷 South Korea": "KR",
    "🇸🇬 Singapore": "SG",
    "🇲🇾 Malaysia": "MY",
    "🇮🇩 Indonesia": "ID",
    "🇳🇿 New Zealand": "NZ",
    "🇧🇷 Brazil": "BR",
    "🇿🇦 South Africa": "ZA",
    "🇹🇷 Turkey": "TR",
    "🇷🇺 Russia": "RU",
}


# Common aliases for manually typed countries
COUNTRY_ALIASES = {
    "usa": "US",
    "us": "US",
    "united states": "US",
    "united states of america": "US",

    "uk": "GB",
    "united kingdom": "GB",
    "great britain": "GB",
    "england": "GB",

    "uae": "AE",
    "united arab emirates": "AE",

    "saudi": "SA",
    "saudi arabia": "SA",

    "india": "IN",
    "bharat": "IN",

    "pakistan": "PK",
    "bangladesh": "BD",
    "nepal": "NP",
    "sri lanka": "LK",

    "australia": "AU",
    "canada": "CA",

    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",

    "japan": "JP",
    "south korea": "KR",
    "korea": "KR",

    "singapore": "SG",
    "malaysia": "MY",
    "indonesia": "ID",

    "new zealand": "NZ",
    "brazil": "BR",
    "south africa": "ZA",
    "turkey": "TR",
    "russia": "RU",
}


# Major timezone choices for countries
# having multiple important timezones.

MULTI_TIMEZONE_OPTIONS = {

    "US": {
        "🇺🇸 New York / Eastern": "America/New_York",
        "🇺🇸 Chicago / Central": "America/Chicago",
        "🇺🇸 Denver / Mountain": "America/Denver",
        "🇺🇸 Los Angeles / Pacific": "America/Los_Angeles",
    },

    "CA": {
        "🇨🇦 Toronto / Eastern": "America/Toronto",
        "🇨🇦 Winnipeg / Central": "America/Winnipeg",
        "🇨🇦 Edmonton / Mountain": "America/Edmonton",
        "🇨🇦 Vancouver / Pacific": "America/Vancouver",
        "🇨🇦 Halifax / Atlantic": "America/Halifax",
    },

    "AU": {
        "🇦🇺 Sydney / Melbourne": "Australia/Sydney",
        "🇦🇺 Brisbane": "Australia/Brisbane",
        "🇦🇺 Adelaide": "Australia/Adelaide",
        "🇦🇺 Perth": "Australia/Perth",
        "🇦🇺 Darwin": "Australia/Darwin",
    },

    "RU": {
        "🇷🇺 Moscow": "Europe/Moscow",
        "🇷🇺 Yekaterinburg": "Asia/Yekaterinburg",
        "🇷🇺 Omsk": "Asia/Omsk",
        "🇷🇺 Krasnoyarsk": "Asia/Krasnoyarsk",
        "🇷🇺 Irkutsk": "Asia/Irkutsk",
        "🇷🇺 Vladivostok": "Asia/Vladivostok",
    },

    "BR": {
        "🇧🇷 São Paulo / Brasilia": "America/Sao_Paulo",
        "🇧🇷 Manaus": "America/Manaus",
        "🇧🇷 Rio Branco": "America/Rio_Branco",
    },

    "ID": {
        "🇮🇩 Jakarta": "Asia/Jakarta",
        "🇮🇩 Makassar": "Asia/Makassar",
        "🇮🇩 Jayapura": "Asia/Jayapura",
    },

    "NZ": {
        "🇳🇿 Auckland": "Pacific/Auckland",
        "🇳🇿 Chatham Islands": "Pacific/Chatham",
    },
}


# ============================================================
# TIMEZONE HELPERS
# ============================================================

def country_code_from_name(country_name):
    """
    Converts a country name typed by the user
    into an ISO country code.
    """

    clean = (
        country_name
        .strip()
        .lower()
    )

    clean = re.sub(
        r"\s+",
        " ",
        clean
    )

    if clean in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[clean]

    try:
        country = pycountry.countries.lookup(
            country_name.strip()
        )

        return country.alpha_2

    except Exception:
        pass

    return None


def get_country_timezones(country_code):
    """
    Returns all pytz timezones for a country.
    """

    return list(
        pytz.country_timezones.get(
            country_code,
            []
        )
    )


def get_default_timezone(country_code):
    """
    For countries with one timezone, use it directly.
    For countries with multiple timezones,
    use a sensible major timezone as fallback.
    """

    if country_code in MULTI_TIMEZONE_OPTIONS:
        return list(
            MULTI_TIMEZONE_OPTIONS[
                country_code
            ].values()
        )[0]

    timezones = get_country_timezones(
        country_code
    )

    if not timezones:
        return None

    return timezones[0]


def get_user_timezone(user_id):
    """
    Get saved user timezone.
    """

    user = users_col.find_one(
        {
            "user_id": user_id
        }
    )

    if not user:
        return None

    timezone_name = user.get(
        "timezone"
    )

    if not timezone_name:
        return None

    try:
        return ZoneInfo(
            timezone_name
        )

    except Exception:
        return None


def save_user_timezone(
    user_id,
    timezone_name,
    country_code=None,
    country_name=None
):
    """
    Save timezone information.
    """

    users_col.update_many(
        {
            "user_id": user_id
        },
        {
            "$set": {
                "timezone": timezone_name,
                "country_code": country_code,
                "country_name": country_name,
                "timezone_updated_at":
                    datetime.now().timestamp()
            }
        }
    )


def format_user_time(
    timestamp,
    timezone
):
    dt = datetime.fromtimestamp(
        timestamp,
        timezone
    )

    return dt.strftime(
        "%d %b %Y, %I:%M %p"
    )


def format_ist_time(
    timestamp
):
    return format_user_time(
        timestamp,
        IST
    )


# ============================================================
# COUNTRY SELECTION
# ============================================================

def show_country_selection(
    chat_id,
    message_text="🌍 Please select your country:"
):
    markup = InlineKeyboardMarkup(
        row_width=2
    )

    buttons = []

    for country_name in COUNTRY_BUTTONS:
        buttons.append(
            InlineKeyboardButton(
                country_name,
                callback_data=(
                    "country:"
                    + COUNTRY_BUTTONS[
                        country_name
                    ]
                )
            )
        )

    buttons.append(
        InlineKeyboardButton(
            "🌎 Other Country",
            callback_data="country:OTHER"
        )
    )

    markup.add(
        *buttons
    )

    bot.send_message(
        chat_id,
        message_text,
        reply_markup=markup
    )


def show_timezone_options(
    chat_id,
    country_code
):
    options = MULTI_TIMEZONE_OPTIONS.get(
        country_code
    )

    if not options:
        return False

    markup = InlineKeyboardMarkup(
        row_width=1
    )

    for label, timezone_name in options.items():
        markup.add(
            InlineKeyboardButton(
                label,
                callback_data=(
                    "tz:"
                    + timezone_name
                )
            )
        )

    markup.add(
        InlineKeyboardButton(
            "✍️ Type My City",
            callback_data="tz_city"
        )
    )

    bot.send_message(
        chat_id,
        "🌍 This country has multiple time zones.\n\n"
        "Please select your city/region:",
        reply_markup=markup
    )

    return True


def ask_for_city(
    chat_id
):
    bot.send_message(
        chat_id,
        "✍️ Please type your city or state/region.\n\n"
        "Example:\n"
        "New York\n"
        "California\n"
        "Toronto\n"
        "Sydney",
        reply_markup=ReplyKeyboardRemove()
    )


def ask_for_other_country(
    chat_id
):
    bot.send_message(
        chat_id,
        "🌎 Please type your country name.\n\n"
        "Example:\n"
        "Brazil\n"
        "Mexico\n"
        "Nigeria\n"
        "Sweden",
        reply_markup=ReplyKeyboardRemove()
    )


# ============================================================
# USER TIMEZONE STATE
# ============================================================

# Temporary in-memory state.
# User's actual timezone is stored in MongoDB.

timezone_states = {}


# ============================================================
# PLAN HELPERS
# ============================================================

def format_plan(minutes):

    minutes = int(minutes)

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

    if minutes % 1440 == 0:
        return f"{minutes // 1440} Days"

    return f"{minutes} Minutes"


def format_remaining(
    seconds
):

    if seconds <= 0:
        return "Expired"

    days = seconds // 86400
    seconds %= 86400

    hours = seconds // 3600
    seconds %= 3600

    minutes = seconds // 60
    seconds %= 60

    parts = []

    if days:
        parts.append(
            f"{days}d"
        )

    if hours:
        parts.append(
            f"{hours}h"
        )

    if minutes:
        parts.append(
            f"{minutes}m"
        )

    if not parts:
        parts.append(
            f"{seconds}s"
        )

    return " ".join(
        parts
    )


# ============================================================
# SEND CHANNEL PLANS
# ============================================================

def send_channel_plans(
    chat_id,
    channel_id
):

    channel = channels_col.find_one(
        {
            "channel_id": channel_id
        }
    )

    if not channel:
        bot.send_message(
            chat_id,
            "❌ Channel not found."
        )
        return

    plans = channel.get(
        "plans",
        {}
    )

    markup = InlineKeyboardMarkup(
        row_width=1
    )

    for minutes, price in plans.items():

        markup.add(
            InlineKeyboardButton(
                f"{format_plan(int(minutes))} - ₹{price}",
                callback_data=(
                    f"plan:{channel_id}:{minutes}"
                )
            )
        )

    markup.add(
        InlineKeyboardButton(
            f"💎 Premium Contact @{CONTACT_USERNAME}",
            url=f"https://t.me/{CONTACT_USERNAME}"
        )
    )

    bot.send_message(
        chat_id,
        "💎 Please select your subscription plan:",
        reply_markup=markup
    )


# ============================================================
# /START
# ============================================================

@bot.message_handler(
    commands=["start"]
)
def start_command(
    message
):

    user_id = message.from_user.id

    parts = (
        message.text or ""
    ).split(
        maxsplit=1
    )

    channel_id = None

    if len(parts) == 2:
        channel_id = parts[1]

    # --------------------------------------------------------
    # Deep link
    # --------------------------------------------------------

    if channel_id:

        try:
            channel_id = int(
                channel_id
            )
        except Exception:
            bot.send_message(
                message.chat.id,
                "❌ Invalid channel link."
            )
            return

        channel = channels_col.find_one(
            {
                "channel_id": channel_id
            }
        )

        if not channel:
            bot.send_message(
                message.chat.id,
                "❌ Channel not found."
            )
            return

        # Save subscription record
        users_col.update_one(
            {
                "user_id": user_id,
                "channel_id": channel_id
            },
            {
                "$set": {
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "first_name":
                        message.from_user.first_name,
                    "username":
                        message.from_user.username,
                }
            },
            upsert=True
        )

        timezone = get_user_timezone(
            user_id
        )

        if timezone is None:

            timezone_states[
                user_id
            ] = {
                "action": "subscription",
                "channel_id": channel_id
            }

            show_country_selection(
                message.chat.id,
                "🌍 Please select your country:"
            )

            return

        send_channel_plans(
            message.chat.id,
            channel_id
        )

        return

    # --------------------------------------------------------
    # Normal /start
    # --------------------------------------------------------

    if user_id == ADMIN_ID:

        markup = InlineKeyboardMarkup()

        markup.add(
            InlineKeyboardButton(
                "📋 Channels",
                callback_data="admin_channels"
            )
        )

        bot.send_message(
            message.chat.id,
            "👑 Admin Panel",
            reply_markup=markup
        )

        return

    # Normal user
    timezone = get_user_timezone(
        user_id
    )

    if timezone is None:

        timezone_states[
            user_id
        ] = {
            "action": "normal"
        }

        show_country_selection(
            message.chat.id,
            "🌍 Please select your country:"
        )

        return

    bot.send_message(
        message.chat.id,
        "👋 Welcome!\n\n"
        "Please use the subscription link "
        "provided by the admin."
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

    timezone_states[
        message.from_user.id
    ] = {
        "action": "timezone"
    }

    show_country_selection(
        message.chat.id,
        "🌍 Please select your country again:"
    )


# ============================================================
# COUNTRY CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("country:")
)
def country_callback(
    call
):

    user_id = call.from_user.id

    country_code = call.data.split(
        ":",
        1
    )[1]

    bot.answer_callback_query(
        call.id
    )

    if country_code == "OTHER":

        timezone_states[
            user_id
        ] = {
            **timezone_states.get(
                user_id,
                {}
            ),
            "waiting_country": True
        }

        ask_for_other_country(
            call.message.chat.id
        )

        return

    country_name = None

    for name, code in COUNTRY_BUTTONS.items():
        if code == country_code:
            country_name = name
            break

    # --------------------------------------------------------
    # Multiple timezone country
    # --------------------------------------------------------

    if country_code in MULTI_TIMEZONE_OPTIONS:

        timezone_states[
            user_id
        ] = {
            **timezone_states.get(
                user_id,
                {}
            ),
            "country_code": country_code,
            "country_name": country_name,
            "waiting_country": False
        }

        bot.edit_message_text(
            "🌍 Please select your city/region:",
            call.message.chat.id,
            call.message.message_id
        )

        show_timezone_options(
            call.message.chat.id,
            country_code
        )

        return

    # --------------------------------------------------------
    # Single timezone country
    # --------------------------------------------------------

    timezone_name = get_default_timezone(
        country_code
    )

    if not timezone_name:

        bot.send_message(
            call.message.chat.id,
            "❌ I couldn't detect the timezone "
            "for this country.\n\n"
            "Please use /timezone and try again."
        )

        return

    save_user_timezone(
        user_id,
        timezone_name,
        country_code,
        country_name
    )

    state = timezone_states.pop(
        user_id,
        {}
    )

    bot.edit_message_text(
        "✅ Country selected successfully!\n\n"
        f"🌍 Country: {country_name}\n"
        f"🕐 Timezone: {timezone_name}",
        call.message.chat.id,
        call.message.message_id
    )

    # Continue subscription flow
    if state.get("action") == "subscription":

        channel_id = state.get(
            "channel_id"
        )

        if channel_id:
            send_channel_plans(
                call.message.chat.id,
                channel_id
            )

    else:

        bot.send_message(
            call.message.chat.id,
            "✅ Your timezone has been saved.\n\n"
            "You can now use your subscription link."
        )


# ============================================================
# TIMEZONE CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("tz:")
)
def timezone_callback(
    call
):

    user_id = call.from_user.id

    timezone_name = call.data.split(
        ":",
        1
    )[1]

    bot.answer_callback_query(
        call.id
    )

    try:
        ZoneInfo(
            timezone_name
        )
    except Exception:

        bot.send_message(
            call.message.chat.id,
            "❌ Invalid timezone."
        )

        return

    state = timezone_states.get(
        user_id,
        {}
    )

    save_user_timezone(
        user_id,
        timezone_name,
        state.get("country_code"),
        state.get("country_name")
    )

    state = timezone_states.pop(
        user_id,
        {}
    )

    bot.edit_message_text(
        "✅ Timezone set successfully!\n\n"
        f"🕐 Timezone: {timezone_name}",
        call.message.chat.id,
        call.message.message_id
    )

    if state.get("action") == "subscription":

        channel_id = state.get(
            "channel_id"
        )

        if channel_id:

            send_channel_plans(
                call.message.chat.id,
                channel_id
            )

    else:

        bot.send_message(
            call.message.chat.id,
            "✅ Your timezone has been updated."
        )


# ============================================================
# CITY BUTTON
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data == "tz_city"
)
def timezone_city_callback(
    call
):

    bot.answer_callback_query(
        call.id
    )

    user_id = call.from_user.id

    state = timezone_states.get(
        user_id,
        {}
    )

    state["waiting_city"] = True

    timezone_states[
        user_id
    ] = state

    ask_for_city(
        call.message.chat.id
    )


# ============================================================
# MANUAL COUNTRY / CITY MESSAGE
# ============================================================

@bot.message_handler(
    func=lambda message:
        (
            message.from_user.id in timezone_states
            and
            (
                timezone_states[
                    message.from_user.id
                ].get("waiting_country")
                or
                timezone_states[
                    message.from_user.id
                ].get("waiting_city")
            )
        )
)
def manual_timezone_input(
    message
):

    user_id = message.from_user.id

    state = timezone_states.get(
        user_id,
        {}
    )

    text = (
        message.text or ""
    ).strip()

    # --------------------------------------------------------
    # MANUAL COUNTRY
    # --------------------------------------------------------

    if state.get(
        "waiting_country"
    ):

        country_code = country_code_from_name(
            text
        )

        if not country_code:

            bot.send_message(
                message.chat.id,
                "❌ I couldn't find that country.\n\n"
                "Please type the full country name.\n\n"
                "Example: Mexico"
            )

            return

        country_name = text

        # Multi timezone
        if country_code in MULTI_TIMEZONE_OPTIONS:

            timezone_states[
                user_id
            ] = {
                **state,
                "country_code": country_code,
                "country_name": country_name,
                "waiting_country": False
            }

            show_timezone_options(
                message.chat.id,
                country_code
            )

            return

        timezone_name = get_default_timezone(
            country_code
        )

        if not timezone_name:

            bot.send_message(
                message.chat.id,
                "❌ I couldn't determine the timezone "
                "for this country.\n\n"
                "Please use /timezone again."
            )

            return

        save_user_timezone(
            user_id,
            timezone_name,
            country_code,
            country_name
        )

        state = timezone_states.pop(
            user_id,
            {}
        )

        bot.send_message(
            message.chat.id,
            "✅ Country detected!\n\n"
            f"🌍 Country: {country_name}\n"
            f"🕐 Timezone: {timezone_name}"
        )

        if state.get(
            "action"
        ) == "subscription":

            channel_id = state.get(
                "channel_id"
            )

            if channel_id:
                send_channel_plans(
                    message.chat.id,
                    channel_id
                )

        return

    # --------------------------------------------------------
    # MANUAL CITY
    # --------------------------------------------------------

    if state.get(
        "waiting_city"
    ):

        country_code = state.get(
            "country_code"
        )

        country_name = state.get(
            "country_name"
        )

        options = MULTI_TIMEZONE_OPTIONS.get(
            country_code,
            {}
        )

        text_lower = text.lower()

        selected_timezone = None

        for label, timezone_name in options.items():

            if text_lower in label.lower():

                selected_timezone = timezone_name
                break

            # Check timezone city/region words
            city_part = (
                label.split(
                    "/"
                )[0]
                .replace("🇺🇸", "")
                .replace("🇨🇦", "")
                .replace("🇦🇺", "")
                .replace("🇷🇺", "")
                .replace("🇧🇷", "")
                .replace("🇮🇩", "")
                .replace("🇳🇿", "")
                .strip()
            )

            if text_lower in city_part.lower():

                selected_timezone = timezone_name
                break

        if not selected_timezone:

            bot.send_message(
                message.chat.id,
                "❌ I couldn't match that city.\n\n"
                "Please select one of the available "
                "timezone options above."
            )

            show_timezone_options(
                message.chat.id,
                country_code
            )

            return

        save_user_timezone(
            user_id,
            selected_timezone,
            country_code,
            country_name
        )

        state = timezone_states.pop(
            user_id,
            {}
        )

        bot.send_message(
            message.chat.id,
            "✅ Timezone set successfully!\n\n"
            f"🌍 Country: {country_name}\n"
            f"🏙 Location: {text}\n"
            f"🕐 Timezone: {selected_timezone}"
        )

        if state.get(
            "action"
        ) == "subscription":

            channel_id = state.get(
                "channel_id"
            )

            if channel_id:

                send_channel_plans(
                    message.chat.id,
                    channel_id
                )

        return


# ============================================================
# /CHANNELS
# ============================================================

@bot.message_handler(
    commands=["channels"]
)
def channels_command(
    message
):

    if message.from_user.id != ADMIN_ID:
        return

    channels = list(
        channels_col.find()
    )

    if not channels:

        bot.send_message(
            message.chat.id,
            "No channels found."
        )

        return

    text = "📋 Channels:\n\n"

    for channel in channels:

        text += (
            f"• {channel.get('name', 'Unknown')}\n"
            f"ID: {channel.get('channel_id')}\n\n"
        )

    bot.send_message(
        message.chat.id,
        text
    )


# ============================================================
# /ADD
# ============================================================

@bot.message_handler(
    commands=["add"]
)
def add_command(
    message
):

    if message.from_user.id != ADMIN_ID:
        return

    bot.send_message(
        message.chat.id,
        "➕ Please forward a message from the channel "
        "you want to add."
    )


# ============================================================
# FORWARDED CHANNEL MESSAGE
# ============================================================

@bot.message_handler(
    content_types=["text"]
)
def forwarded_channel_message(
    message
):

    if message.from_user.id != ADMIN_ID:
        return

    if not message.forward_from_chat:
        return

    channel = message.forward_from_chat

    if channel.type != "channel":
        return

    existing = channels_col.find_one(
        {
            "channel_id": channel.id
        }
    )

    if existing:

        bot.send_message(
            message.chat.id,
            "⚠️ This channel is already added."
        )

        return

    bot.send_message(
        message.chat.id,
        f"📢 Channel detected:\n\n"
        f"Name: {channel.title}\n"
        f"ID: {channel.id}\n\n"
        "Now send plans in this format:\n\n"
        "1:10,1440:50,10080:100"
    )

    bot.register_next_step_handler(
        message,
        receive_plans,
        channel.id,
        channel.title
    )


def receive_plans(
    message,
    channel_id,
    channel_name
):

    if message.from_user.id != ADMIN_ID:
        return

    text = (
        message.text or ""
    ).strip()

    try:

        plans = {}

        for item in text.split(","):

            minutes, price = item.split(
                ":"
            )

            minutes = int(
                minutes.strip()
            )

            price = float(
                price.strip()
            )

            plans[str(minutes)] = price

    except Exception:

        bot.send_message(
            message.chat.id,
            "❌ Invalid format.\n\n"
            "Example:\n"
            "1:10,1440:50,10080:100"
        )

        return

    channels_col.insert_one(
        {
            "channel_id": channel_id,
            "name": channel_name,
            "plans": plans,
            "admin_id": ADMIN_ID,
            "created_at":
                datetime.now().timestamp()
        }
    )

    bot.send_message(
        message.chat.id,
        "✅ Channel added successfully!"
    )


# ============================================================
# PLAN CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("plan:")
)
def plan_callback(
    call
):

    bot.answer_callback_query(
        call.id
    )

    try:

        _, channel_id, minutes = (
            call.data.split(":")
        )

        channel_id = int(
            channel_id
        )

        minutes = int(
            minutes
        )

    except Exception:

        bot.send_message(
            call.message.chat.id,
            "❌ Invalid plan."
        )

        return

    channel = channels_col.find_one(
        {
            "channel_id": channel_id
        }
    )

    if not channel:
        return

    plans = channel.get(
        "plans",
        {}
    )

    price = plans.get(
        str(minutes)
    )

    if price is None:
        return

    payment_id = (
        f"{call.from_user.id}_"
        f"{channel_id}_"
        f"{minutes}_"
        f"{int(datetime.now().timestamp())}"
    )

    upi_link = (
        "upi://pay?"
        f"pa={UPI_ID}"
        f"&pn=Premium"
        f"&am={price}"
        "&cu=INR"
    )

    qr_url = (
        "https://api.qrserver.com/v1/create-qr-code/"
        "?size=300x300"
        f"&data={upi_link}"
    )

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "💳 I Have Paid",
            callback_data=(
                f"paid:{channel_id}:"
                f"{minutes}:{payment_id}"
            )
        )
    )

    bot.send_photo(
        call.message.chat.id,
        qr_url,
        caption=(
            "💎 Premium Subscription\n\n"
            f"📦 Plan: {format_plan(minutes)}\n"
            f"💰 Amount: ₹{price}\n\n"
            f"UPI ID: `{UPI_ID}`\n\n"
            "After payment, click "
            "I Have Paid."
        ),
        parse_mode="Markdown",
        reply_markup=markup
    )


# ============================================================
# PAYMENT CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("paid:")
)
def paid_callback(
    call
):

    try:

        _, channel_id, minutes, payment_id = (
            call.data.split(":")
        )

        channel_id = int(
            channel_id
        )

        minutes = int(
            minutes
        )

    except Exception:

        bot.answer_callback_query(
            call.id,
            "Invalid payment request."
        )

        return

    existing = users_col.find_one(
        {
            "user_id": call.from_user.id,
            "channel_id": channel_id,
            "status": "payment_pending"
        }
    )

    if existing:

        bot.answer_callback_query(
            call.id,
            "Your payment is already under review."
        )

        return

    users_col.update_one(
        {
            "user_id": call.from_user.id,
            "channel_id": channel_id
        },
        {
            "$set": {
                "status": "payment_pending",
                "plan_minutes": minutes,
                "payment_id": payment_id,
                "requested_at":
                    datetime.now().timestamp(),
                "first_name":
                    call.from_user.first_name,
                "username":
                    call.from_user.username
            }
        },
        upsert=True
    )

    bot.answer_callback_query(
        call.id,
        "Payment submitted!"
    )

    bot.send_message(
        call.message.chat.id,
        "✅ Payment request submitted!\n\n"
        "Please wait for admin approval."
    )

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "✅ Approve",
            callback_data=(
                f"approve:{channel_id}:"
                f"{call.from_user.id}"
            )
        ),
        InlineKeyboardButton(
            "❌ Reject",
            callback_data=(
                f"reject:{channel_id}:"
                f"{call.from_user.id}"
            )
        )
    )

    username = (
        f"@{call.from_user.username}"
        if call.from_user.username
        else "No username"
    )

    bot.send_message(
        ADMIN_ID,
        "💳 New Payment Request\n\n"
        f"👤 User: {call.from_user.first_name}\n"
        f"🔗 Username: {username}\n"
        f"🆔 ID: {call.from_user.id}\n"
        f"📦 Plan: {format_plan(minutes)}\n\n"
        "Payment submitted for approval.",
        reply_markup=markup
    )


# ============================================================
# APPROVE
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("approve:")
)
def approve_callback(
    call
):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(
            call.id,
            "Owner only."
        )

        return

    try:

        _, channel_id, user_id = (
            call.data.split(":")
        )

        channel_id = int(
            channel_id
        )

        user_id = int(
            user_id
        )

    except Exception:
        return

    subscription = users_col.find_one(
        {
            "user_id": user_id,
            "channel_id": channel_id
        }
    )

    if not subscription:
        return

    minutes = int(
        subscription.get(
            "plan_minutes",
            0
        )
    )

    # Timer DOES NOT start here.
    # It starts only when user joins.

    users_col.update_one(
        {
            "user_id": user_id,
            "channel_id": channel_id
        },
        {
            "$set": {
                "status": "waiting",
                "plan_minutes": minutes,
                "approved_at":
                    datetime.now().timestamp()
            },
            "$unset": {
                "joined_at": "",
                "expiry": "",
                "invite_link": ""
            }
        }
    )

    try:

        invite = bot.create_chat_invite_link(
            channel_id,
            member_limit=1
        )

        invite_link = invite.invite_link

        users_col.update_one(
            {
                "user_id": user_id,
                "channel_id": channel_id
            },
            {
                "$set": {
                    "invite_link": invite_link
                }
            }
        )

    except Exception as e:

        bot.send_message(
            ADMIN_ID,
            "❌ Could not create invite link.\n\n"
            f"Error: {e}"
        )

        return

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "🚀 Join Channel",
            url=invite_link
        )
    )

    bot.send_message(
        user_id,
        "✅ Payment Approved!\n\n"
        f"📦 Plan: {format_plan(minutes)}\n\n"
        "⚠️ Your subscription timer has NOT started yet.\n\n"
        "👉 Join the channel using the button below.\n"
        "⏱️ Timer will start automatically when you join.",
        reply_markup=markup
    )

    bot.answer_callback_query(
        call.id,
        "Approved!"
    )

    bot.edit_message_reply_markup(
        call.message.chat.id,
        call.message.message_id,
        reply_markup=None
    )


# ============================================================
# REJECT
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("reject:")
)
def reject_callback(
    call
):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(
            call.id,
            "Owner only."
        )

        return

    try:

        _, channel_id, user_id = (
            call.data.split(":")
        )

        channel_id = int(
            channel_id
        )

        user_id = int(
            user_id
        )

    except Exception:
        return

    users_col.delete_one(
        {
            "user_id": user_id,
            "channel_id": channel_id,
            "status": "payment_pending"
        }
    )

    bot.send_message(
        user_id,
        "❌ Payment Request Rejected!\n\n"
        "Please complete the payment and then "
        "click I Have Paid."
    )

    bot.answer_callback_query(
        call.id,
        "Rejected!"
    )

    bot.edit_message_reply_markup(
        call.message.chat.id,
        call.message.message_id,
        reply_markup=None
    )


# ============================================================
# CHANNEL JOIN DETECTION
# ============================================================

@bot.chat_member_handler()
def track_channel_join(
    update
):

    try:

        user = update.new_chat_member.user

        channel_id = update.chat.id

        new_status = (
            update.new_chat_member.status
        )

        old_status = (
            update.old_chat_member.status
        )

    except Exception:
        return

    joined_statuses = {
        "member",
        "administrator"
    }

    if new_status not in joined_statuses:
        return

    # Already a member -> don't restart timer
    if old_status in joined_statuses:
        return

    subscription = users_col.find_one(
        {
            "user_id": user.id,
            "channel_id": channel_id,
            "status": "waiting"
        }
    )

    if not subscription:
        return

    plan_minutes = int(
        subscription.get(
            "plan_minutes",
            0
        )
    )

    if plan_minutes <= 0:
        return

    # ========================================================
    # TIMER STARTS HERE
    # ========================================================

    joined_at = datetime.now()

    expiry_datetime = (
        joined_at
        + timedelta(
            minutes=plan_minutes
        )
    )

    joined_timestamp = (
        joined_at.timestamp()
    )

    expiry_timestamp = (
        expiry_datetime.timestamp()
    )

    users_col.update_one(
        {
            "user_id": user.id,
            "channel_id": channel_id
        },
        {
            "$set": {
                "status": "active",
                "joined_at": joined_timestamp,
                "expiry": expiry_timestamp
            },
            "$unset": {
                "invite_link": ""
            }
        }
    )

    # ========================================================
    # USER TIME
    # ========================================================

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
        user_timezone
    )

    bot.send_message(
        user.id,
        "🎉 Subscription Started!\n\n"
        f"📦 Plan: {format_plan(plan_minutes)}\n\n"
        f"🟢 Started: {user_joined_text}\n"
        f"🔴 Expires: {user_expiry_text}\n"
        f"🕐 Timezone: {timezone_name}\n\n"
        "Your subscription timer is now running."
    )

    # ========================================================
    # ADMIN TIME ALWAYS IST
    # ========================================================

    admin_joined_text = format_ist_time(
        joined_timestamp
    )

    admin_expiry_text = format_ist_time(
        expiry_timestamp
    )

    bot.send_message(
        ADMIN_ID,
        "🟢 User Joined Channel\n\n"
        f"👤 Name: {user.first_name}\n"
        f"🆔 ID: {user.id}\n"
        f"📦 Plan: {format_plan(plan_minutes)}\n\n"
        f"🟢 Joined: {admin_joined_text} IST\n"
        f"🔴 Expiry: {admin_expiry_text} IST"
    )


# ============================================================
# /USERS
# ============================================================

@bot.message_handler(
    commands=["users"]
)
def users_command(
    message
):

    if message.from_user.id != ADMIN_ID:
        return

    records = list(
        users_col.find(
            {
                "status": {
                    "$ne": "payment_pending"
                }
            }
        ).sort(
            "expiry",
            1
        )
    )

    if not records:

        bot.send_message(
            message.chat.id,
            "No users found."
        )

        return

    chunks = []
    current = ""

    now = datetime.now().timestamp()

    for user in records:

        user_id = user.get(
            "user_id"
        )

        channel_id = user.get(
            "channel_id"
        )

        status = user.get(
            "status",
            "unknown"
        )

        first_name = user.get(
            "first_name",
            "Unknown"
        )

        username = user.get(
            "username"
        )

        username_text = (
            f"@{username}"
            if username
            else "No username"
        )

        text = (
            "👤 USER\n"
            "━━━━━━━━━━━━━━\n"
            f"Name: {first_name}\n"
            f"Username: {username_text}\n"
            f"Telegram ID: {user_id}\n"
            f"Channel ID: {channel_id}\n"
            f"Status: {status}\n"
        )

        if status == "waiting":

            text += (
                "Joined: Not joined yet\n"
                "Expiry: Not started yet\n"
                "Remaining: Not started yet\n"
            )

        elif status == "active":

            joined_ts = user.get(
                "joined_at"
            )

            expiry_ts = user.get(
                "expiry"
            )

            if joined_ts and expiry_ts:

                remaining = (
                    int(expiry_ts - now)
                )

                text += (
                    f"Joined: "
                    f"{format_ist_time(joined_ts)} IST\n"
                    f"Expiry: "
                    f"{format_ist_time(expiry_ts)} IST\n"
                    f"Remaining: "
                    f"{format_remaining(remaining)}\n"
                )

        else:

            text += (
                "Joined: N/A\n"
                "Expiry: N/A\n"
                "Remaining: N/A\n"
            )

        text += (
            "━━━━━━━━━━━━━━\n\n"
        )

        if len(
            current
        ) + len(text) > 4000:

            chunks.append(
                current
            )

            current = text

        else:

            current += text

    if current:
        chunks.append(
            current
        )

    for chunk in chunks:

        bot.send_message(
            message.chat.id,
            chunk
        )


# ============================================================
# EXPIRY / KICK SYSTEM
# ============================================================

def kick_expired_users():

    now = datetime.now().timestamp()

    expired_users = users_col.find(
        {
            "status": "active",
            "expiry": {
                "$lte": now
            }
        }
    )

    for subscription in expired_users:

        user_id = subscription.get(
            "user_id"
        )

        channel_id = subscription.get(
            "channel_id"
        )

        try:

            # Ban
            bot.ban_chat_member(
                channel_id,
                user_id
            )

            # Immediately unban so user can rejoin
            bot.unban_chat_member(
                channel_id,
                user_id
            )

        except Exception as e:

            print(
                "Kick error:",
                e
            )

        try:

            renewal_link = (
                f"https://t.me/"
                f"{bot.get_me().username}"
                f"?start={channel_id}"
            )

            markup = InlineKeyboardMarkup()

            markup.add(
                InlineKeyboardButton(
                    "🔄 Renew Subscription",
                    url=renewal_link
                )
            )

            bot.send_message(
                user_id,
                "⏰ Subscription Expired!\n\n"
                "Your premium subscription has expired.\n\n"
                "Click below to renew:",
                reply_markup=markup
            )

        except Exception as e:

            print(
                "Expiry message error:",
                e
            )

        # Delete active subscription
        users_col.delete_one(
            {
                "_id":
                    subscription["_id"]
            }
        )

        print(
            f"Expired user removed: "
            f"{user_id} from {channel_id}"
        )


# ============================================================
# START BOT
# ============================================================

if __name__ == "__main__":

    keep_alive()

    scheduler = BackgroundScheduler()

    scheduler.add_job(
        kick_expired_users,
        "interval",
        minutes=1
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