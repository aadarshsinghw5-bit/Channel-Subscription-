import os
import re
import telebot

from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
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
# RENDER KEEP-ALIVE SERVER
# ============================================================

app = Flask("")


@app.route("/")
def home():
    return "Bot is running and healthy!"


def run_web():
    port = int(os.environ.get("PORT", 5000))

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
ADMIN_ID = int(os.getenv("ADMIN_ID"))
UPI_ID = os.getenv("UPI_ID")
CONTACT_USERNAME = os.getenv("CONTACT_USERNAME")


bot = telebot.TeleBot(BOT_TOKEN)


# ============================================================
# TIMEZONE
# ============================================================

IST = ZoneInfo("Asia/Kolkata")


# ============================================================
# MONGODB
# ============================================================

client = MongoClient(MONGO_URI)

db = client["sub_management"]

channels_col = db["channels"]
users_col = db["users"]


# ============================================================
# COUNTRY TIMEZONE DATA
# ============================================================

COUNTRIES = {
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
    "🇲🇽 Mexico": "MX",
    "🇳🇬 Nigeria": "NG",
    "🇰🇪 Kenya": "KE",
    "🇪🇬 Egypt": "EG",
    "🇵🇭 Philippines": "PH",
    "🇹🇭 Thailand": "TH",
    "🇻🇳 Vietnam": "VN",
}


COUNTRY_ALIASES = {
    "india": "IN",
    "bharat": "IN",

    "usa": "US",
    "us": "US",
    "america": "US",
    "united states": "US",
    "united states of america": "US",

    "uk": "GB",
    "england": "GB",
    "britain": "GB",
    "great britain": "GB",
    "united kingdom": "GB",

    "uae": "AE",
    "united arab emirates": "AE",

    "saudi": "SA",
    "saudi arabia": "SA",

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
    "mexico": "MX",
    "nigeria": "NG",
    "kenya": "KE",
    "egypt": "EG",
    "philippines": "PH",
    "thailand": "TH",
    "vietnam": "VN",
}


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
        "🇧🇷 Sao Paulo / Brasilia": "America/Sao_Paulo",
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


timezone_states = {}


# ============================================================
# TIMEZONE HELPERS
# ============================================================

def country_code_from_name(country_name):

    clean = country_name.strip().lower()

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
        return None


def get_country_timezones(country_code):

    return list(
        pytz.country_timezones.get(
            country_code,
            []
        )
    )


def get_default_timezone(country_code):

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

    user = users_col.find_one(
        {
            "user_id": user_id,
            "timezone": {
                "$exists": True
            }
        },
        {
            "timezone": 1
        }
    )

    if user and user.get("timezone"):

        try:
            return ZoneInfo(
                user["timezone"]
            )

        except Exception:
            pass

    return None


def save_user_timezone(
    user_id,
    timezone_name,
    country_code=None,
    country_name=None
):

    users_col.update_many(
        {
            "user_id": user_id
        },
        {
            "$set": {
                "timezone": timezone_name,
                "country_code": country_code,
                "country_name": country_name
            }
        }
    )

    users_col.update_one(
        {
            "user_id": user_id
        },
        {
            "$set": {
                "user_id": user_id,
                "timezone": timezone_name,
                "country_code": country_code,
                "country_name": country_name
            }
        },
        upsert=True
    )


def format_user_time(timestamp, timezone):

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


def format_ist_time(timestamp):

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


# ============================================================
# COUNTRY SELECTION
# ============================================================

def show_country_selection(chat_id):

    markup = InlineKeyboardMarkup(
        row_width=2
    )

    buttons = []

    for country_name, country_code in COUNTRIES.items():

        buttons.append(
            InlineKeyboardButton(
                country_name,
                callback_data=f"country_{country_code}"
            )
        )

    buttons.append(
        InlineKeyboardButton(
            "🌎 Other Country",
            callback_data="country_OTHER"
        )
    )

    markup.add(*buttons)

    bot.send_message(
        chat_id,
        "🌍 *Please select your country:*",
        reply_markup=markup,
        parse_mode="Markdown"
    )


def show_timezone_options(
    chat_id,
    country_code
):

    options = MULTI_TIMEZONE_OPTIONS.get(
        country_code
    )

    if not options:
        return

    markup = InlineKeyboardMarkup(
        row_width=1
    )

    for label, timezone_name in options.items():

        markup.add(
            InlineKeyboardButton(
                label,
                callback_data=f"tz_{timezone_name}"
            )
        )

    bot.send_message(
        chat_id,
        "🌍 *Please select your region/city:*",
        reply_markup=markup,
        parse_mode="Markdown"
    )


def ask_other_country(chat_id):

    bot.send_message(
        chat_id,
        "🌎 *Please type your country name:*\n\n"
        "Example: `Mexico`",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )


def ask_city(chat_id):

    bot.send_message(
        chat_id,
        "🏙 *Please type your city or region:*\n\n"
        "Example:\n"
        "New York\n"
        "California\n"
        "Toronto\n"
        "Sydney",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )


# ============================================================
# HELPER FUNCTIONS
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

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m"

    if hours > 0:
        return f"{hours}h {minutes}m"

    if minutes > 0:
        return f"{minutes}m {secs}s"

    return f"{secs}s"


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

    markup = InlineKeyboardMarkup()

    for p_time, p_price in ch_data["plans"].items():

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

    markup.add(

        InlineKeyboardButton(

            "📞 Contact Admin",

            url=f"https://t.me/{CONTACT_USERNAME}"
        )
    )

    bot.send_message(

        chat_id,

        f"Welcome!\n\n"

        f"You are joining: "
        f"*{ch_data['name']}*.\n\n"

        f"Please select a subscription plan below:",

        reply_markup=markup,

        parse_mode="Markdown"
    )

    return True


# ============================================================
# START
# ============================================================

@bot.message_handler(commands=["start"])
def start_handler(message):

    user_id = message.from_user.id

    text = (message.text or "").split()


    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    if user_id == ADMIN_ID and len(text) == 1:

        bot.send_message(

            message.chat.id,

            "✅ *Admin Panel Active!*\n\n"

            "/add - Add/Edit Channel & Prices\n"
            "/channels - Manage Existing Channels\n"
            "/users - View Subscribers\n"
            "/timezone - Change Your Timezone",

            parse_mode="Markdown"
        )

        return


    # --------------------------------------------------------
    # DEEP LINK
    # --------------------------------------------------------

    if len(text) > 1:

        try:

            ch_id = int(text[1])

            ch_data = channels_col.find_one(
                {
                    "channel_id": ch_id
                }
            )

            if not ch_data:
                return


            users_col.update_one(

                {
                    "user_id": user_id,
                    "channel_id": ch_id
                },

                {
                    "$set": {

                        "user_id": user_id,

                        "channel_id": ch_id,

                        "name":
                            message.from_user.first_name,

                        "username":
                            message.from_user.username or ""

                    }
                },

                upsert=True
            )


            timezone = get_user_timezone(
                user_id
            )


            if timezone is None:

                users_col.update_one(

                    {
                        "user_id": user_id,
                        "channel_id": ch_id
                    },

                    {
                        "$set": {
                            "pending_channel_id": ch_id
                        }
                    }
                )

                timezone_states[user_id] = {
                    "action": "subscription",
                    "channel_id": ch_id
                }

                show_country_selection(
                    message.chat.id
                )

                return


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

            timezone_states[user_id] = {
                "action": "normal"
            }

            show_country_selection(
                message.chat.id
            )

        else:

            bot.send_message(

                message.chat.id,

                "Welcome!\n\n"

                "To join a channel, please use the link "
                "provided by the Admin."
            )


# ============================================================
# COUNTRY CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("country_")
)
def country_selected(call):

    user_id = call.from_user.id

    country_code = call.data.split(
        "_",
        1
    )[1]

    bot.answer_callback_query(
        call.id
    )

    if country_code == "OTHER":

        state = timezone_states.get(
            user_id,
            {
                "action": "normal"
            }
        )

        state["waiting_country"] = True

        timezone_states[user_id] = state

        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None
        )

        ask_other_country(
            call.message.chat.id
        )

        return


    country_name = "Unknown"

    for name, code in COUNTRIES.items():

        if code == country_code:
            country_name = name
            break


    if country_code in MULTI_TIMEZONE_OPTIONS:

        state = timezone_states.get(
            user_id,
            {
                "action": "normal"
            }
        )

        state["country_code"] = country_code
        state["country_name"] = country_name
        state["waiting_country"] = False
        state["waiting_city"] = False

        timezone_states[user_id] = state

        bot.edit_message_text(
            "🌍 *Please select your region/city:*",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )

        show_timezone_options(
            call.message.chat.id,
            country_code
        )

        return


    timezone_name = get_default_timezone(
        country_code
    )

    if not timezone_name:

        bot.send_message(
            call.message.chat.id,
            "❌ Timezone could not be detected.\n\n"
            "Please select another country."
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
        "✅ *Country selected successfully!*\n\n"
        f"🌍 Country: {country_name}\n"
        f"🕐 Timezone: `{timezone_name}`",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )


    if state.get("action") == "subscription":

        ch_id = state.get(
            "channel_id"
        )

        if ch_id:

            users_col.update_one(
                {
                    "user_id": user_id,
                    "channel_id": int(ch_id)
                },
                {
                    "$unset": {
                        "pending_channel_id": ""
                    }
                }
            )

            send_channel_plans(
                call.message.chat.id,
                int(ch_id)
            )

    else:

        bot.send_message(
            call.message.chat.id,
            "Your timezone has been saved successfully."
        )


# ============================================================
# TIMEZONE CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("tz_")
)
def timezone_selected(call):

    user_id = call.from_user.id

    timezone_name = call.data.split(
        "_",
        1
    )[1]

    bot.answer_callback_query(
        call.id
    )

    try:
        ZoneInfo(timezone_name)
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
        "✅ *Timezone set successfully!*\n\n"
        f"🕐 Timezone: `{timezone_name}`",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )


    if state.get("action") == "subscription":

        ch_id = state.get(
            "channel_id"
        )

        if ch_id:

            users_col.update_one(
                {
                    "user_id": user_id,
                    "channel_id": int(ch_id)
                },
                {
                    "$unset": {
                        "pending_channel_id": ""
                    }
                }
            )

            send_channel_plans(
                call.message.chat.id,
                int(ch_id)
            )

    else:

        bot.send_message(
            call.message.chat.id,
            "Your timezone has been updated successfully."
        )


# ============================================================
# MANUAL COUNTRY / CITY
# ============================================================

@bot.message_handler(
    func=lambda message:
        message.from_user.id in timezone_states
        and (
            timezone_states[
                message.from_user.id
            ].get("waiting_country")
            or
            timezone_states[
                message.from_user.id
            ].get("waiting_city")
        )
)
def manual_timezone_input(message):

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

    if state.get("waiting_country"):

        country_code = country_code_from_name(
            text
        )

        if not country_code:

            bot.send_message(
                message.chat.id,
                "❌ Country not found.\n\n"
                "Please type the correct country name.\n\n"
                "Example: `Mexico`",
                parse_mode="Markdown"
            )

            return


        country_name = text


        if country_code in MULTI_TIMEZONE_OPTIONS:

            state["country_code"] = country_code
            state["country_name"] = country_name
            state["waiting_country"] = False
            state["waiting_city"] = False

            timezone_states[user_id] = state

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
                "for this country."
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
            "✅ *Country detected successfully!*\n\n"
            f"🌍 Country: {country_name}\n"
            f"🕐 Timezone: `{timezone_name}`",
            parse_mode="Markdown"
        )


        if state.get("action") == "subscription":

            ch_id = state.get(
                "channel_id"
            )

            if ch_id:

                users_col.update_one(
                    {
                        "user_id": user_id,
                        "channel_id": int(ch_id)
                    },
                    {
                        "$unset": {
                            "pending_channel_id": ""
                        }
                    }
                )

                send_channel_plans(
                    message.chat.id,
                    int(ch_id)
                )

        return


    # --------------------------------------------------------
    # MANUAL CITY
    # --------------------------------------------------------

    if state.get("waiting_city"):

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

            clean_label = re.sub(
                r"[^\w\s/.-]",
                "",
                label.lower()
            )

            clean_text = re.sub(
                r"[^\w\s/.-]",
                "",
                text_lower
            )

            if clean_text in clean_label:

                selected_timezone = timezone_name
                break


            if clean_text in timezone_name.lower():

                selected_timezone = timezone_name
                break


            city_parts = (
                clean_label
                .split("/")
            )

            for part in city_parts:

                if clean_text in part.strip():

                    selected_timezone = timezone_name
                    break

            if selected_timezone:
                break


        if not selected_timezone:

            bot.send_message(
                message.chat.id,
                "❌ I couldn't match that city.\n\n"
                "Please select one of the available "
                "timezone options."
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
            "✅ *Timezone set successfully!*\n\n"
            f"🌍 Country: {country_name}\n"
            f"🏙 Location: {text}\n"
            f"🕐 Timezone: `{selected_timezone}`",
            parse_mode="Markdown"
        )


        if state.get("action") == "subscription":

            ch_id = state.get(
                "channel_id"
            )

            if ch_id:

                users_col.update_one(
                    {
                        "user_id": user_id,
                        "channel_id": int(ch_id)
                    },
                    {
                        "$unset": {
                            "pending_channel_id": ""
                        }
                    }
                )

                send_channel_plans(
                    message.chat.id,
                    int(ch_id)
                )


# ============================================================
# /TIMEZONE
# ============================================================

@bot.message_handler(commands=["timezone"])
def timezone_command(message):

    timezone_states[
        message.from_user.id
    ] = {
        "action": "timezone"
    }

    show_country_selection(
        message.chat.id
    )


# ============================================================
# CHANNELS
# ============================================================

@bot.message_handler(
    commands=["channels"],
    func=lambda m: m.from_user.id == ADMIN_ID
)
def list_channels(message):

    markup = InlineKeyboardMarkup()

    cursor = channels_col.find(
        {
            "admin_id": ADMIN_ID
        }
    )

    count = 0

    for ch in cursor:

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
    func=lambda m: m.from_user.id == ADMIN_ID
)
def add_channel_start(message):

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
    func=lambda call: call.data == "add_new"
)
def cb_add_new(call):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(

            call.id,

            "⛔ Only Owner can add channels!",

            show_alert=True
        )

        return


    bot.answer_callback_query(call.id)


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

def get_plans(message):

    if message.from_user.id != ADMIN_ID:
        return


    if message.forward_from_chat:

        ch_id = message.forward_from_chat.id

        ch_name = message.forward_from_chat.title


        msg = bot.send_message(

            ADMIN_ID,

            f"Channel Detected: *{ch_name}*\n\n"

            "Enter plans in format:\n"
            "`Minutes:Price, Minutes:Price`\n\n"

            "Example:\n"
            "`1:10, 1440:99, 10080:199, "
            "43200:399, 129600:799`\n\n"

            "This means:\n"
            "1 Minute\n"
            "1 Day\n"
            "7 Days\n"
            "30 Days\n"
            "90 Days",

            parse_mode="Markdown"
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

        raw_plans = message.text.split(",")

        plans_dict = {}


        for p in raw_plans:

            t, pr = p.strip().split(":")

            t = str(int(t.strip()))

            pr = pr.strip()

            plans_dict[t] = pr


        channels_col.update_one(

            {
                "channel_id": ch_id
            },

            {
                "$set": {

                    "name": ch_name,

                    "plans": plans_dict,

                    "admin_id": ADMIN_ID

                }
            },

            upsert=True
        )


        bot_username = bot.get_me().username

        bot.send_message(

            ADMIN_ID,

            f"✅ *Setup Successful!*\n\n"

            f"Invite Link for users:\n"
            f"`https://t.me/{bot_username}?start={ch_id}`",

            parse_mode="Markdown"
        )


    except Exception:

        bot.send_message(

            ADMIN_ID,

            "❌ Invalid format.\n\n"

            "Use:\n"
            "`1:10, 1440:99, 10080:199, "
            "43200:399, 129600:799`",

            parse_mode="Markdown"
        )


# ============================================================
# USER SELECTS PLAN
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("select_")
)
def user_pays(call):

    try:

        _, ch_id, mins = call.data.split("_")

        ch_id = int(ch_id)

        mins = int(mins)


        ch_data = channels_col.find_one(
            {
                "channel_id": ch_id
            }
        )


        if not ch_data:
            return


        price = ch_data["plans"][str(mins)]

        plan_name = format_plan(mins)


        qr_url = (

            "https://api.qrserver.com/v1/create-qr-code/"

            "?size=300x300&data="

            f"upi://pay?pa={UPI_ID}"

            f"%26am={price}"

            "%26cu=INR"

        )


        markup = InlineKeyboardMarkup()


        markup.add(

            InlineKeyboardButton(

                "✅ I Have Paid",

                callback_data=(
                    f"paid_{ch_id}_{mins}"
                )
            )
        )


        markup.add(

            InlineKeyboardButton(

                "📞 Contact Admin",

                url=f"https://t.me/{CONTACT_USERNAME}"
            )
        )


        bot.send_photo(

            call.message.chat.id,

            qr_url,

            caption=(

                f"📦 Plan: *{plan_name}*\n"
                f"💰 Price: ₹{price}\n\n"

                f"UPI ID: `{UPI_ID}`\n\n"

                "Please complete the payment and click "
                "*I Have Paid*."
            ),

            reply_markup=markup,

            parse_mode="Markdown"
        )


        bot.answer_callback_query(call.id)


    except Exception as e:

        bot.answer_callback_query(

            call.id,

            "❌ Something went wrong!",

            show_alert=True
        )

        bot.send_message(

            ADMIN_ID,

            f"❌ Payment Flow Error:\n`{e}`",

            parse_mode="Markdown"
        )


# ============================================================
# USER PRESSES I HAVE PAID
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("paid_")
)
def admin_notify(call):

    try:

        _, ch_id, mins = call.data.split("_")

        ch_id = int(ch_id)

        mins = int(mins)


        user = call.from_user


        ch_data = channels_col.find_one(

            {
                "channel_id": ch_id
            }
        )


        if not ch_data:
            return


        price = ch_data["plans"][str(mins)]

        plan_name = format_plan(mins)


        users_col.update_one(

            {
                "user_id": user.id,

                "channel_id": ch_id
            },

            {
                "$set": {

                    "user_id": user.id,

                    "channel_id": ch_id,

                    "name": user.first_name,

                    "username": user.username or "",

                    "plan_minutes": mins,

                    "status": "payment_pending",

                    "requested_at":
                        datetime.now().timestamp()

                }
            },

            upsert=True
        )


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


        bot.send_message(

            ADMIN_ID,

            f"🔔 *Payment Verification Required!*\n\n"

            f"👤 User: {user.first_name}\n"
            f"🆔 User ID: `{user.id}`\n"
            f"📢 Channel: {ch_data['name']}\n"
            f"📦 Plan: {plan_name}\n"
            f"💰 Price: ₹{price}",

            reply_markup=markup,

            parse_mode="Markdown"
        )


        # ----------------------------------------------------
        # USER CONFIRMATION + CONTACT ADMIN
        # ----------------------------------------------------

        u_markup = InlineKeyboardMarkup()

        u_markup.add(

            InlineKeyboardButton(

                "📞 Contact Admin",

                url=f"https://t.me/{CONTACT_USERNAME}"
            )
        )


        bot.send_message(

            call.message.chat.id,

            "✅ Your payment request has been sent.\n\n"
            "Please wait for Admin approval.",

            reply_markup=u_markup
        )


        bot.answer_callback_query(

            call.id,

            "✅ Request sent!"
        )


    except Exception as e:

        bot.answer_callback_query(

            call.id,

            "❌ Error!",

            show_alert=True
        )

        bot.send_message(

            ADMIN_ID,

            f"❌ Payment Request Error:\n`{e}`",

            parse_mode="Markdown"
        )


# ============================================================
# APPROVE PAYMENT
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("app_")
)
def approve_now(call):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(

            call.id,

            "⛔ Only Owner can approve payments!",

            show_alert=True
        )

        return


    try:

        _, u_id, ch_id, mins = call.data.split("_")

        u_id = int(u_id)

        ch_id = int(ch_id)

        mins = int(mins)


        subscription = users_col.find_one(

            {
                "user_id": u_id,

                "channel_id": ch_id
            }
        )


        if not subscription:

            bot.answer_callback_query(

                call.id,

                "❌ User request not found!",

                show_alert=True
            )

            return


        plan_name = format_plan(mins)


        users_col.update_one(

            {
                "_id": subscription["_id"]
            },

            {
                "$set": {

                    "plan_minutes": mins,

                    "status": "waiting",

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


        link = bot.create_chat_invite_link(

            ch_id,

            member_limit=1
        )


        users_col.update_one(

            {
                "_id": subscription["_id"]
            },

            {
                "$set": {

                    "invite_link":
                        link.invite_link

                }
            }
        )


        bot.send_message(

            u_id,

            f"🥳 *Payment Approved!*\n\n"

            f"📦 Subscription: *{plan_name}*\n\n"

            f"🔗 Join Channel:\n"
            f"{link.invite_link}\n\n"

            "⚠️ Your subscription timer will start "
            "*when you join the channel*.",

            parse_mode="Markdown"
        )


        bot.edit_message_text(

            f"✅ *Payment Approved!*\n\n"

            f"👤 User ID: `{u_id}`\n"
            f"📦 Plan: `{plan_name}`\n\n"

            "⏳ Waiting for user to join...\n"
            "Timer has NOT started yet.",

            call.message.chat.id,

            call.message.message_id,

            parse_mode="Markdown"
        )


        bot.answer_callback_query(

            call.id,

            "✅ Payment approved!"
        )


    except Exception as e:

        bot.answer_callback_query(

            call.id,

            "❌ Approval error!",

            show_alert=True
        )


        bot.send_message(

            ADMIN_ID,

            f"❌ Approval Error:\n`{e}`",

            parse_mode="Markdown"
        )


# ============================================================
# REJECT PAYMENT
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("rej_")
)
def reject_payment(call):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(

            call.id,

            "⛔ Only Owner can reject payments!",

            show_alert=True
        )

        return


    try:

        _, u_id, ch_id = call.data.split("_")

        u_id = int(u_id)

        ch_id = int(ch_id)


        users_col.delete_one(

            {
                "user_id": u_id,

                "channel_id": ch_id,

                "status": "payment_pending"
            }
        )


        bot.answer_callback_query(

            call.id,

            "❌ Payment rejected!"
        )


        bot.send_message(

            u_id,

            "❌ *Payment Request Rejected!*\n\n"

            "Please complete the payment and then "
            "click *I Have Paid*.",

            parse_mode="Markdown"
        )


        bot.send_message(

            ADMIN_ID,

            f"❌ *Request Rejected!*\n\n"

            f"User ID: `{u_id}`\n\n"

            "The user has been notified.",

            parse_mode="Markdown"
        )


        bot.edit_message_text(

            f"❌ *Payment Rejected!*\n\n"

            f"User ID: `{u_id}`",

            call.message.chat.id,

            call.message.message_id,

            parse_mode="Markdown"
        )


    except Exception as e:

        bot.answer_callback_query(

            call.id,

            "❌ Rejection error!",

            show_alert=True
        )


        bot.send_message(

            ADMIN_ID,

            f"❌ Rejection Error:\n`{e}`",

            parse_mode="Markdown"
        )


# ============================================================
# TRACK ACTUAL CHANNEL JOIN
# ============================================================

@bot.chat_member_handler()
def track_channel_join(update):

    try:

        new_status = update.new_chat_member.status

        old_status = update.old_chat_member.status

        user = update.new_chat_member.user

        ch_id = update.chat.id


        joined_statuses = [

            "member",

            "administrator"

        ]


        if (

            new_status in joined_statuses

            and old_status in joined_statuses

        ):

            return


        if new_status not in joined_statuses:

            return


        subscription = users_col.find_one(

            {
                "user_id": user.id,

                "channel_id": ch_id,

                "status": "waiting"
            }
        )


        if not subscription:

            return


        # ----------------------------------------------------
        # TIMER STARTS HERE
        # ----------------------------------------------------

        joined_at = datetime.now()

        plan_minutes = int(
            subscription["plan_minutes"]
        )


        expiry_datetime = (

            joined_at

            + timedelta(
                minutes=plan_minutes
            )
        )


        joined_timestamp = joined_at.timestamp()

        expiry_timestamp = expiry_datetime.timestamp()


        users_col.update_one(

            {
                "_id": subscription["_id"]
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
                        user.first_name,

                    "username":
                        user.username or ""

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

            f"👤 *User Joined!*\n\n"

            f"User: {user.first_name}\n"
            f"User ID: `{user.id}`\n"
            f"Channel ID: `{ch_id}`\n\n"

            f"📥 Joined:\n"
            f"{admin_joined_text} IST\n\n"

            f"📦 Subscription:\n"
            f"{plan_name}\n\n"

            f"🔴 Expires:\n"
            f"{admin_expiry_text} IST",

            parse_mode="Markdown"
        )


        # ----------------------------------------------------
        # USER NOTIFICATION
        # ----------------------------------------------------

        bot.send_message(

            user.id,

            f"✅ *Subscription Started!*\n\n"

            f"Your subscription has started now.\n\n"

            f"📦 Duration: *{plan_name}*\n\n"

            f"📥 Joined:\n"
            f"{user_joined_text}\n\n"

            f"🔴 Expires at:\n"
            f"{user_expiry_text}\n\n"

            f"🌍 Timezone: `{timezone_name}`",

            parse_mode="Markdown"
        )


    except Exception as e:

        print(
            "Join tracking error:",
            e
        )


# ============================================================
# /USERS
# ============================================================

@bot.message_handler(
    commands=["users"],
    func=lambda m: m.from_user.id == ADMIN_ID
)
def show_users(message):

    try:

        users = list(
            users_col.find({})
        )


        if not users:

            bot.send_message(

                ADMIN_ID,

                "👥 *Subscribers*\n\n"
                "No users found.",

                parse_mode="Markdown"
            )

            return


        text = "👥 *SUBSCRIBERS*\n\n"

        now = datetime.now().timestamp()

        index = 0


        for user in users:

            status = user.get(
                "status",
                "unknown"
            )


            if status == "payment_pending":
                continue


            index += 1


            user_id = user.get(
                "user_id",
                "Unknown"
            )

            channel_id = user.get(
                "channel_id",
                "Unknown"
            )

            name = user.get(
                "name",
                "Unknown"
            )

            # Prevent Markdown from breaking
            name = str(name).replace(
                "_",
                "\\_"
            ).replace(
                "*",
                "\\*"
            ).replace(
                "`",
                "\\`"
            )


            # ------------------------------------------------
            # WAITING
            # ------------------------------------------------

            if status == "waiting":

                text += (

                    f"{index}. 👤 *{name}*\n"

                    f"🆔 ID: `{user_id}`\n"

                    f"📢 Channel: `{channel_id}`\n"

                    f"🟡 Status: Waiting to join\n"

                    f"⏳ Timer: Not started yet\n\n"

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

                    remaining_seconds = int(

                        expiry_ts - now

                    )

                    remaining = format_remaining(

                        remaining_seconds

                    )

                else:

                    remaining = "Unknown"


                text += (

                    f"{index}. 👤 *{name}*\n"

                    f"🆔 ID: `{user_id}`\n"

                    f"📢 Channel: `{channel_id}`\n"

                    f"🟢 Status: Active\n"

                    f"📥 Joined: {joined_text} IST\n"

                    f"🔴 Expires: {expiry_text} IST\n"

                    f"⏳ Remaining: {remaining}\n\n"

                )

                continue


            # ------------------------------------------------
            # OTHER
            # ------------------------------------------------

            text += (

                f"{index}. 👤 *{name}*\n"

                f"🆔 ID: `{user_id}`\n"

                f"📢 Channel: `{channel_id}`\n"

                f"Status: `{status}`\n\n"

            )


        if index == 0:

            bot.send_message(

                ADMIN_ID,

                "👥 *Subscribers*\n\n"
                "No active/waiting subscribers.",

                parse_mode="Markdown"
            )

            return


        # ----------------------------------------------------
        # SAFE MESSAGE SPLITTING
        # ----------------------------------------------------

        chunks = []

        current_chunk = ""

        for block in text.split("\n\n"):

            block += "\n\n"

            if len(current_chunk) + len(block) > 3900:

                if current_chunk:
                    chunks.append(
                        current_chunk
                    )

                current_chunk = block

            else:

                current_chunk += block


        if current_chunk:
            chunks.append(
                current_chunk
            )


        for chunk in chunks:

            bot.send_message(

                ADMIN_ID,

                chunk,

                parse_mode="Markdown"
            )


    except Exception as e:

        print(
            "Users command error:",
            e
        )

        bot.send_message(

            ADMIN_ID,

            "❌ Unable to load subscribers.\n\n"
            "Please try /users again."
        )


# ============================================================
# MANAGE CHANNEL
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("manage_")
)
def manage_ch(call):

    if call.from_user.id != ADMIN_ID:

        bot.answer_callback_query(

            call.id,

            "⛔ Only Owner can manage channels!",

            show_alert=True
        )

        return


    try:

        ch_id = int(
            call.data.split("_")[1]
        )


        ch_data = channels_col.find_one(

            {
                "channel_id": ch_id
            }
        )


        if not ch_data:

            bot.answer_callback_query(

                call.id,

                "❌ Channel not found!",

                show_alert=True
            )

            return


        bot_username = bot.get_me().username

        link = (

            f"https://t.me/"
            f"{bot_username}"
            f"?start={ch_id}"
        )


        bot.edit_message_text(

            f"⚙️ Settings for: "
            f"*{ch_data['name']}*\n\n"

            f"Your Link:\n"
            f"`{link}`\n\n"

            "To edit prices, use /add and "
            "forward a message from this channel again.",

            call.message.chat.id,

            call.message.message_id,

            parse_mode="Markdown"
        )


        bot.answer_callback_query(call.id)


    except Exception:

        bot.answer_callback_query(

            call.id,

            "❌ Error!",

            show_alert=True
        )


# ============================================================
# AUTOMATICALLY KICK EXPIRED USERS
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


    bot_username = bot.get_me().username


    for user in expired_users:

        try:

            user_id = user["user_id"]

            channel_id = user["channel_id"]


            # ------------------------------------------------
            # REMOVE USER
            # ------------------------------------------------

            bot.ban_chat_member(

                channel_id,

                user_id
            )


            bot.unban_chat_member(

                channel_id,

                user_id
            )


            # ------------------------------------------------
            # RENEW LINK
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

            bot.send_message(

                user_id,

                "⚠️ *Your subscription has expired.*\n\n"

                "Your channel access has been removed.\n\n"

                "To join again or renew, click "
                "the button below.",

                reply_markup=markup,

                parse_mode="Markdown"
            )


            # ------------------------------------------------
            # DELETE SUBSCRIPTION
            # ------------------------------------------------

            users_col.delete_one(

                {
                    "_id": user["_id"]
                }
            )


        except Exception as e:

            print(
                "Expiry error:",
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

        minutes=1
    )


    scheduler.start()


    bot.remove_webhook()


    print("Bot is running...")


    bot.infinity_polling(

        timeout=20,

        long_polling_timeout=10,

        allowed_updates=[

            "message",

            "callback_query",

            "chat_member"

        ]
    )