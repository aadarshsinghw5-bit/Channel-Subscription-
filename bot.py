import os
import time
import html
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


if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing.")

if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable is missing.")

if not UPI_ID:
    raise ValueError("UPI_ID environment variable is missing.")


bot = telebot.TeleBot(BOT_TOKEN)


# ============================================================
# TIMEZONE
# ============================================================

IST = ZoneInfo("Asia/Kolkata")


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

client = MongoClient(MONGO_URI)

db = client["sub_management"]

channels_col = db["channels"]

users_col = db["users"]

profiles_col = db["profiles"]


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


def get_user_timezone(user_id):
    profile = profiles_col.find_one(
        {
            "user_id": user_id
        },
        {
            "timezone": 1
        }
    )

    if profile and profile.get("timezone"):
        try:
            return ZoneInfo(profile["timezone"])
        except Exception:
            pass

    return None


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


def get_contact_username():
    if not CONTACT_USERNAME:
        return "Admin"

    username = CONTACT_USERNAME.strip()

    if not username.startswith("@"):
        username = "@" + username

    return username


def get_contact_url():
    if not CONTACT_USERNAME:
        return None

    username = CONTACT_USERNAME.strip().lstrip("@")

    if not username:
        return None

    return f"https://t.me/{username}"


# ============================================================
# TIMEZONE SELECTOR
# ============================================================

def show_timezone_request(chat_id):
    markup = InlineKeyboardMarkup()

    row = []

    for index, (country, timezone_name) in enumerate(
        COUNTRY_BUTTONS
    ):
        row.append(
            InlineKeyboardButton(
                country,
                callback_data=f"tz_{index}"
            )
        )

        if len(row) == 2:
            markup.row(*row)
            row = []

    if row:
        markup.row(*row)

    markup.add(
        InlineKeyboardButton(
            "✍️ Other Country",
            callback_data="tz_manual"
        )
    )

    bot.send_message(
        chat_id,
        "🌍 *Please select your country*",
        reply_markup=markup,
        parse_mode="Markdown"
    )


def save_timezone(
    user_id,
    timezone_name,
    chat_id
):
    try:
        ZoneInfo(timezone_name)
    except Exception:
        return False

    profiles_col.update_one(
        {
            "user_id": user_id
        },
        {
            "$set": {
                "user_id": user_id,
                "timezone": timezone_name
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


def country_timezones(country_name):
    aliases = {
        "india": "India",
        "pakistan": "Pakistan",
        "bangladesh": "Bangladesh",
        "nepal": "Nepal",
        "sri lanka": "Sri Lanka",
        "uae": "United Arab Emirates",
        "dubai": "United Arab Emirates",
        "saudi": "Saudi Arabia",
        "usa": "United States",
        "us": "United States",
        "united states": "United States",
        "uk": "United Kingdom",
        "england": "United Kingdom"
    }

    clean_name = " ".join(
        country_name.strip().split()
    )

    clean_name = aliases.get(
        clean_name.lower(),
        clean_name
    )

    try:
        country = pycountry.countries.search_fuzzy(
            clean_name
        )[0]

        code = country.alpha_2

        return pytz.country_timezones.get(
            code,
            []
        )

    except Exception:
        return []


def timezone_choice_keyboard(choices):
    markup = InlineKeyboardMarkup()

    for index, timezone_name in enumerate(choices):
        readable = timezone_name.split("/")[-1]

        readable = readable.replace(
            "_",
            " "
        )

        markup.add(
            InlineKeyboardButton(
                f"🌍 {readable}",
                callback_data=f"tzpick_{index}"
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
        f"You Are Joining *{ch_data['name']}*\n\n"
        f"💎 Please Select Your Subscription Plan:",
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

            # ------------------------------------------------
            # SAVE USER BASIC INFO
            # ------------------------------------------------

            existing_user = users_col.find_one(
                {
                    "user_id": user_id,
                    "channel_id": ch_id
                }
            )

            if existing_user:
                users_col.update_one(
                    {
                        "_id": existing_user["_id"]
                    },
                    {
                        "$set": {
                            "name":
                                message.from_user.first_name,

                            "username":
                                message.from_user.username or ""
                        }
                    }
                )

            else:
                users_col.insert_one(
                    {
                        "user_id": user_id,

                        "channel_id": ch_id,

                        "name":
                            message.from_user.first_name,

                        "username":
                            message.from_user.username or ""
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
                        "user_id": user_id,
                        "channel_id": ch_id
                    },
                    {
                        "$set": {
                            "pending_channel_id": ch_id
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
                "To join a channel, please use the link "
                "provided by the Admin."
            )


# ============================================================
# TIMEZONE COUNTRY CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("tz_")
        and not call.data.startswith("tzpick_")
)
def timezone_country_callback(call):
    user_id = call.from_user.id

    try:
        if call.data == "tz_manual":
            profiles_col.update_one(
                {
                    "user_id": user_id
                },
                {
                    "$set": {
                        "user_id": user_id,
                        "awaiting_country": True
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
            call.data.split("_")[1]
        )

        country, timezone_name = COUNTRY_BUTTONS[
            index
        ]

        save_timezone(
            user_id,
            timezone_name,
            call.message.chat.id
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
        bot.answer_callback_query(
            call.id,
            "❌ Timezone error!",
            show_alert=True
        )

        try:
            bot.send_message(
                ADMIN_ID,
                f"❌ Timezone Error:\n`{e}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ============================================================
# MULTIPLE TIMEZONE CALLBACK
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("tzpick_")
)
def timezone_multi_callback(call):
    user_id = call.from_user.id

    try:
        index = int(
            call.data.split("_")[1]
        )

        profile = profiles_col.find_one(
            {
                "user_id": user_id
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

        if index < 0 or index >= len(choices):
            bot.answer_callback_query(
                call.id,
                "❌ Invalid timezone.",
                show_alert=True
            )

            return

        timezone_name = choices[index]

        save_timezone(
            user_id,
            timezone_name,
            call.message.chat.id
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
        bot.answer_callback_query(
            call.id,
            "❌ Timezone error!",
            show_alert=True
        )

        try:
            bot.send_message(
                ADMIN_ID,
                f"❌ Timezone Error:\n`{e}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ============================================================
# MANUAL COUNTRY INPUT
# ============================================================

def waiting_for_country(message):
    profile = profiles_col.find_one(
        {
            "user_id": message.from_user.id,
            "awaiting_country": True
        }
    )

    return bool(profile)


@bot.message_handler(
    content_types=["text"],
    func=waiting_for_country
)
def manual_country_handler(message):
    if (message.text or "").startswith("/"):
        return

    user_id = message.from_user.id

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

        save_timezone(
            user_id,
            timezone_name,
            message.chat.id
        )

        bot.send_message(
            message.chat.id,
            "✅ Timezone Saved!"
        )

        return

    # --------------------------------------------------------
    # MULTIPLE TIMEZONES
    # --------------------------------------------------------

    profiles_col.update_one(
        {
            "user_id": user_id
        },
        {
            "$set": {
                "timezone_choices": zones
            },
            "$unset": {
                "awaiting_country": ""
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

@bot.message_handler(commands=["timezone"])
def timezone_command(message):
    show_timezone_request(
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
    func=lambda call:
        call.data == "add_new"
)
def cb_add_new(call):
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

            t = str(
                int(t.strip())
            )

            pr = pr.strip()

            plans_dict[t] = pr

        if not plans_dict:
            raise ValueError("No plans found.")

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
    func=lambda call:
        call.data.startswith("select_")
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

        price = plans[str(mins)]

        plan_name = format_plan(
            mins
        )

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

        contact_url = get_contact_url()

        if contact_url:
            markup.add(
                InlineKeyboardButton(
                    "📞 Contact Admin",
                    url=contact_url
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
                "*I Have Paid*.\n\n"
                f"Admin: {get_contact_username()}"
            ),
            reply_markup=markup,
            parse_mode="Markdown"
        )

        bot.answer_callback_query(
            call.id
        )

    except Exception as e:
        bot.answer_callback_query(
            call.id,
            "❌ Something went wrong!",
            show_alert=True
        )

        try:
            bot.send_message(
                ADMIN_ID,
                f"❌ Payment Flow Error:\n`{e}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ============================================================
# USER PRESSES I HAVE PAID
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("paid_")
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

        price = plans[str(mins)]

        plan_name = format_plan(
            mins
        )

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
                        time.time()
                },

                "$unset": {
                    "joined_at": "",

                    "expiry": "",

                    "invite_link": "",

                    "invite_link_expires_at": ""
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

        u_markup = InlineKeyboardMarkup()

        contact_url = get_contact_url()

        if contact_url:
            u_markup.add(
                InlineKeyboardButton(
                    "📞 Contact Admin",
                    url=contact_url
                )
            )

        bot.send_message(
            call.message.chat.id,
            "✅ Your payment request has been sent.\n\n"
            "Please wait for Admin approval.\n\n"
            f"Admin: {get_contact_username()}",
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

        try:
            bot.send_message(
                ADMIN_ID,
                f"❌ Payment Request Error:\n`{e}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ============================================================
# APPROVE PAYMENT
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("app_")
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

                "channel_id": ch_id,

                "status": "payment_pending"
            }
        )

        if not subscription:
            bot.answer_callback_query(
                call.id,
                "❌ User request not found!",
                show_alert=True
            )

            return

        plan_name = format_plan(
            mins
        )

        # ----------------------------------------------------
        # WAITING STATE
        # ----------------------------------------------------

        users_col.update_one(
            {
                "_id": subscription["_id"]
            },
            {
                "$set": {
                    "plan_minutes": mins,

                    "status": "waiting",

                    "approved_at":
                        time.time()
                },

                "$unset": {
                    "joined_at": "",

                    "expiry": "",

                    "invite_link": "",

                    "invite_link_expires_at": ""
                }
            }
        )

        # ----------------------------------------------------
        # TEMPORARY ONE-PERSON INVITE LINK
        # ----------------------------------------------------

        now_timestamp = int(
            time.time()
        )

        invite_expiry_timestamp = (
            now_timestamp
            + (mins * 60)
        )

        invite_expiry_datetime = datetime.fromtimestamp(
            invite_expiry_timestamp,
            ZoneInfo("UTC")
        )

        link = bot.create_chat_invite_link(
            ch_id,
            member_limit=1,
            expire_date=invite_expiry_datetime
        )

        users_col.update_one(
            {
                "_id": subscription["_id"]
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

        try:
            bot.send_message(
                ADMIN_ID,
                f"❌ Approval Error:\n`{e}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ============================================================
# REJECT PAYMENT
# ============================================================

@bot.callback_query_handler(
    func=lambda call:
        call.data.startswith("rej_")
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

        try:
            bot.send_message(
                ADMIN_ID,
                f"❌ Rejection Error:\n`{e}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass


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

        joined_timestamp = time.time()

        plan_minutes = int(
            subscription["plan_minutes"]
        )

        expiry_timestamp = (
            joined_timestamp
            + (plan_minutes * 60)
        )

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

        timezone_name = str(
            getattr(
                user_timezone,
                "key",
                "Asia/Kolkata"
            )
        )

        bot.send_message(
            user.id,
            f"✅ *Subscription Started!*\n\n"
            "Your subscription has started now.\n\n"
            f"📦 Duration: *{plan_name}*\n\n"
            f"📥 Joined:\n"
            f"{user_joined_text}\n\n"
            f"🔴 Expires at:\n"
            f"{user_expiry_text}\n\n"
            f"🌍 Timezone: `{timezone_name}`",
            parse_mode="Markdown"
        )

    except Exception as e:
        try:
            bot.send_message(
                ADMIN_ID,
                f"❌ Join Tracking Error:\n`{e}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass


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
            users_col.find(
                {
                    "channel_id": {
                        "$exists": True
                    }
                }
            )
        )

        text = "👥 *SUBSCRIBERS*\n\n"

        now = time.time()

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

            name = html.escape(
                str(
                    user.get(
                        "name",
                        "Unknown"
                    )
                )
            )

            # ------------------------------------------------
            # WAITING
            # ------------------------------------------------

            if status == "waiting":
                text += (
                    f"{index}. 👤 <b>{name}</b>\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"📢 Channel: <code>{channel_id}</code>\n"
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
                    f"{index}. 👤 <b>{name}</b>\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"📢 Channel: <code>{channel_id}</code>\n"
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
                f"{index}. 👤 <b>{name}</b>\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"📢 Channel: <code>{channel_id}</code>\n"
                f"Status: "
                f"<code>{html.escape(str(status))}</code>\n\n"
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

            if (
                len(current_chunk) + len(block)
                > 3900
            ):
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
        call.data.startswith("manage_")
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

        bot.answer_callback_query(
            call.id
        )

    except Exception:
        bot.answer_callback_query(
            call.id,
            "❌ Error!",
            show_alert=True
        )


# ============================================================
# AUTOMATICALLY HANDLE EXPIRED USERS
# ============================================================

def kick_expired_users():
    now = time.time()

    expired_users = users_col.find(
        {
            "status": "active",

            "expiry": {
                "$lte": now
            }
        }
    )

    try:
        bot_username = bot.get_me().username
    except Exception:
        bot_username = ""

    for user in expired_users:
        try:
            user_id = user["user_id"]

            channel_id = user["channel_id"]

            # ------------------------------------------------
            # REVOKE CHANNEL ACCESS
            #
            # We restrict the expired member instead of using
            # ban + unban, so we don't intentionally place them
            # into Telegram's Removed Users list.
            # ------------------------------------------------

            try:
                bot.restrict_chat_member(
                    channel_id,
                    user_id,
                    permissions=telebot.types.ChatPermissions(
                        can_send_messages=False,

                        can_send_audios=False,

                        can_send_documents=False,

                        can_send_photos=False,

                        can_send_videos=False,

                        can_send_video_notes=False,

                        can_send_voice_notes=False,

                        can_send_polls=False,

                        can_send_other_messages=False,

                        can_add_web_page_previews=False
                    )
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

            bot.send_message(
                user_id,
                "⏰ *Subscription Expired!*\n\n"
                "Your premium subscription has expired.\n\n"
                "Click below to renew:",
                reply_markup=markup,
                parse_mode="Markdown"
            )

            # ------------------------------------------------
            # DELETE OLD SUBSCRIPTION
            # ------------------------------------------------

            users_col.delete_one(
                {
                    "_id": user["_id"]
                }
            )

        except Exception as e:
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"❌ Expiry Error:\n`{e}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass


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
