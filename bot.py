import os
import time
import html
from urllib.parse import quote

import telebot
import pycountry
import pytz

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from threading import Thread


# ============================================================
# RENDER KEEP-ALIVE SERVER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is running and healthy!"


def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    Thread(target=run_web, daemon=True).start()


# ============================================================
# CONFIGURATION
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")
UPI_ID = os.getenv("UPI_ID")
CONTACT_USERNAME = os.getenv("CONTACT_USERNAME")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable is missing.")

if not ADMIN_ID_RAW:
    raise RuntimeError("ADMIN_ID environment variable is missing.")

ADMIN_ID = int(ADMIN_ID_RAW)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)


# ============================================================
# TIMEZONE
# ============================================================

IST = ZoneInfo("Asia/Kolkata")


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
    ("🇹🇷 Turkey", "Europe/Istanbul"),
]


# ============================================================
# MONGODB
# ============================================================

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
db = client["sub_management"]

channels_col = db["channels"]
users_col = db["users"]
profiles_col = db["profiles"]


# ============================================================
# SAFE TEXT HELPERS
# ============================================================

def esc(value):
    return html.escape(str(value), quote=False)


def get_contact_username():
    if not CONTACT_USERNAME:
        return "Admin"

    username = CONTACT_USERNAME.strip()
    if not username:
        return "Admin"

    return username if username.startswith("@") else "@" + username


def get_contact_url():
    if not CONTACT_USERNAME:
        return None

    username = CONTACT_USERNAME.strip().lstrip("@")
    if not username:
        return None

    return f"https://t.me/{username}"


def answer_callback(call, text=None, show_alert=False):
    try:
        bot.answer_callback_query(
            call.id,
            text=text,
            show_alert=show_alert
        )
    except Exception:
        pass


def send_admin_error(title, error):
    try:
        bot.send_message(
            ADMIN_ID,
            (
                f"<b>{esc(title)}</b>\n\n"
                f"<code>{esc(error)}</code>"
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass


# ============================================================
# PLAN / TIME HELPERS
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


def format_time(timestamp, timezone):
    if not timestamp:
        return "Unknown"

    try:
        return datetime.fromtimestamp(
            float(timestamp),
            timezone
        ).strftime("%d %b %Y, %I:%M:%S %p")
    except Exception:
        return "Unknown"


def format_ist_time(timestamp):
    return format_time(timestamp, IST)


# ============================================================
# USER TIMEZONE
# ============================================================

def get_user_timezone(user_id):
    profile = profiles_col.find_one(
        {"user_id": user_id},
        {"timezone": 1}
    )

    if profile and profile.get("timezone"):
        try:
            return ZoneInfo(profile["timezone"])
        except Exception:
            pass

    return None


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
        "england": "United Kingdom",
    }

    clean_name = " ".join(country_name.strip().split())
    clean_name = aliases.get(clean_name.lower(), clean_name)

    try:
        country = pycountry.countries.search_fuzzy(clean_name)[0]
        return pytz.country_timezones.get(country.alpha_2, [])
    except Exception:
        return []


def timezone_choice_keyboard(choices):
    markup = InlineKeyboardMarkup()

    for index, timezone_name in enumerate(choices):
        readable = timezone_name.split("/")[-1].replace("_", " ")
        markup.add(
            InlineKeyboardButton(
                f"🌍 {readable}",
                callback_data=f"tzpick_{index}"
            )
        )

    return markup


def show_timezone_request(chat_id):
    markup = InlineKeyboardMarkup()
    row = []

    for index, (country, _) in enumerate(COUNTRY_BUTTONS):
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
        "🌍 <b>Please select your country</b>",
        reply_markup=markup,
        parse_mode="HTML"
    )


def save_timezone(user_id, timezone_name, chat_id):
    try:
        ZoneInfo(timezone_name)
    except Exception:
        return False

    profiles_col.update_one(
        {"user_id": user_id},
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

    pending = users_col.find_one(
        {
            "user_id": user_id,
            "pending_channel_id": {"$exists": True}
        }
    )

    if pending:
        ch_id = pending.get("pending_channel_id")

        users_col.update_one(
            {"_id": pending["_id"]},
            {"$unset": {"pending_channel_id": ""}}
        )

        if ch_id:
            send_channel_plans(chat_id, int(ch_id))

    return True


# ============================================================
# CHANNEL PLANS
# ============================================================

def send_channel_plans(chat_id, ch_id):
    ch_data = channels_col.find_one({"channel_id": ch_id})

    if not ch_data:
        bot.send_message(
            chat_id,
            "❌ Channel not found."
        )
        return False

    markup = InlineKeyboardMarkup()

    plans = ch_data.get("plans", {})

    for p_time, p_price in plans.items():
        try:
            minutes = int(p_time)
            label = format_plan(minutes)

            markup.add(
                InlineKeyboardButton(
                    f"💳 {label} - ₹{p_price}",
                    callback_data=f"select_{ch_id}_{minutes}"
                )
            )
        except Exception:
            continue

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
            f"You Are Joining <b>{esc(ch_data.get('name', 'Channel'))}</b>\n\n"
            "💎 <b>Please Select Your Subscription Plan:</b>"
        ),
        reply_markup=markup,
        parse_mode="HTML"
    )

    return True


# ============================================================
# START
# ============================================================

@bot.message_handler(commands=["start"])
def start_handler(message):
    user_id = message.from_user.id
    parts = (message.text or "").split()

    # ADMIN
    if user_id == ADMIN_ID and len(parts) == 1:
        bot.send_message(
            message.chat.id,
            (
                "✅ <b>Admin Panel Active!</b>\n\n"
                "/add - Add/Edit Channel & Prices\n"
                "/channels - Manage Existing Channels\n"
                "/users - View Subscribers\n"
                "/timezone - Change Your Timezone"
            ),
            parse_mode="HTML"
        )
        return

    # DEEP LINK
    if len(parts) > 1:
        try:
            ch_id = int(parts[1])

            ch_data = channels_col.find_one(
                {"channel_id": ch_id}
            )

            if not ch_data:
                bot.send_message(
                    message.chat.id,
                    "❌ This channel is not configured."
                )
                return

            existing_user = users_col.find_one(
                {
                    "user_id": user_id,
                    "channel_id": ch_id
                }
            )

            user_data = {
                "user_id": user_id,
                "channel_id": ch_id,
                "name": message.from_user.first_name or "",
                "username": message.from_user.username or ""
            }

            if existing_user:
                users_col.update_one(
                    {"_id": existing_user["_id"]},
                    {"$set": user_data}
                )
            else:
                users_col.insert_one(user_data)

            timezone = get_user_timezone(user_id)

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

                show_timezone_request(message.chat.id)
                return

            send_channel_plans(message.chat.id, ch_id)
            return

        except Exception as e:
            send_admin_error("Start deep-link error", e)
            bot.send_message(
                message.chat.id,
                "❌ Something went wrong. Please try again."
            )
            return

    # NORMAL START
    if user_id != ADMIN_ID:
        timezone = get_user_timezone(user_id)

        if timezone is None:
            show_timezone_request(message.chat.id)
        else:
            bot.send_message(
                message.chat.id,
                (
                    "Welcome! 👋\n\n"
                    "To join a channel, please use the link "
                    "provided by the Admin."
                )
            )


# ============================================================
# TIMEZONE CALLBACKS
# ============================================================

@bot.callback_query_handler(
    func=lambda call: (
        call.data.startswith("tz_")
        and not call.data.startswith("tzpick_")
    )
)
def timezone_country_callback(call):
    user_id = call.from_user.id

    try:
        if call.data == "tz_manual":
            profiles_col.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "awaiting_country": True
                    }
                },
                upsert=True
            )

            answer_callback(call)

            bot.send_message(
                call.message.chat.id,
                "✍️ Please type your country name.\n\nExample: India"
            )
            return

        index = int(call.data.split("_")[1])
        _, timezone_name = COUNTRY_BUTTONS[index]

        save_timezone(
            user_id,
            timezone_name,
            call.message.chat.id
        )

        answer_callback(call, "✅ Timezone Saved!")

        try:
            bot.delete_message(
                call.message.chat.id,
                call.message.message_id
            )
        except Exception:
            pass

    except Exception as e:
        answer_callback(
            call,
            "❌ Timezone error!",
            show_alert=True
        )
        send_admin_error("Timezone error", e)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("tzpick_")
)
def timezone_multi_callback(call):
    user_id = call.from_user.id

    try:
        index = int(call.data.split("_")[1])

        profile = profiles_col.find_one(
            {"user_id": user_id}
        )

        if not profile:
            answer_callback(
                call,
                "❌ Please try again.",
                show_alert=True
            )
            return

        choices = profile.get("timezone_choices", [])

        if index < 0 or index >= len(choices):
            answer_callback(
                call,
                "❌ Invalid timezone.",
                show_alert=True
            )
            return

        save_timezone(
            user_id,
            choices[index],
            call.message.chat.id
        )

        answer_callback(call, "✅ Timezone Saved!")

        try:
            bot.delete_message(
                call.message.chat.id,
                call.message.message_id
            )
        except Exception:
            pass

    except Exception as e:
        answer_callback(
            call,
            "❌ Timezone error!",
            show_alert=True
        )
        send_admin_error("Timezone choice error", e)


# ============================================================
# MANUAL COUNTRY
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
    zones = country_timezones(message.text or "")

    if not zones:
        bot.send_message(
            message.chat.id,
            "❌ Country not found.\n\nPlease enter a valid country name."
        )
        return

    if len(zones) == 1:
        save_timezone(
            user_id,
            zones[0],
            message.chat.id
        )

        bot.send_message(
            message.chat.id,
            "✅ Timezone Saved!"
        )
        return

    profiles_col.update_one(
        {"user_id": user_id},
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

    bot.send_message(
        message.chat.id,
        "🌍 This country has multiple timezones.\n\n"
        "Please select your timezone:",
        reply_markup=timezone_choice_keyboard(zones)
    )


# ============================================================
# /TIMEZONE
# ============================================================

@bot.message_handler(commands=["timezone"])
def timezone_command(message):
    show_timezone_request(message.chat.id)


# ============================================================
# CHANNEL MANAGEMENT
# ============================================================

@bot.message_handler(
    commands=["channels"],
    func=lambda m: m.from_user.id == ADMIN_ID
)
def list_channels(message):
    markup = InlineKeyboardMarkup()
    count = 0

    for ch in channels_col.find({"admin_id": ADMIN_ID}):
        markup.add(
            InlineKeyboardButton(
                f"Channel: {ch.get('name', 'Unknown')}",
                callback_data=f"manage_{ch['channel_id']}"
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
            "No channels found.\n\nClick below to add one.",
            reply_markup=markup
        )
    else:
        bot.send_message(
            ADMIN_ID,
            "Your Managed Channels:",
            reply_markup=markup
        )


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

    bot.register_next_step_handler(msg, get_plans)


@bot.callback_query_handler(
    func=lambda call: call.data == "add_new"
)
def cb_add_new(call):
    if call.from_user.id != ADMIN_ID:
        answer_callback(
            call,
            "⛔ Only Owner can add channels!",
            show_alert=True
        )
        return

    answer_callback(call)

    msg = bot.send_message(
        ADMIN_ID,
        "Please FORWARD any message from your channel here."
    )

    bot.register_next_step_handler(msg, get_plans)


def get_plans(message):
    if message.from_user.id != ADMIN_ID:
        return

    if not message.forward_from_chat:
        bot.send_message(
            ADMIN_ID,
            "❌ Error: Message was not forwarded.\n\nUse /add to try again."
        )
        return

    ch_id = message.forward_from_chat.id
    ch_name = message.forward_from_chat.title or "Channel"

    msg = bot.send_message(
        ADMIN_ID,
        (
            f"Channel Detected: <b>{esc(ch_name)}</b>\n\n"
            "Enter plans in format:\n"
            "<code>Minutes:Price, Minutes:Price</code>\n\n"
            "Example:\n"
            "<code>1:10, 1440:99, 10080:199, 43200:399, 129600:799</code>\n\n"
            "This means:\n"
            "1 Minute\n"
            "1 Day\n"
            "7 Days\n"
            "30 Days\n"
            "90 Days"
        ),
        parse_mode="HTML"
    )

    bot.register_next_step_handler(
        msg,
        finalize_channel,
        ch_id,
        ch_name
    )


def finalize_channel(message, ch_id, ch_name):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        raw_plans = (message.text or "").split(",")
        plans_dict = {}

        for item in raw_plans:
            t, price = item.strip().split(":", 1)

            minutes = str(int(t.strip()))
            price = price.strip()

            if not price:
                raise ValueError("Empty price.")

            float(price)

            plans_dict[minutes] = price

        if not plans_dict:
            raise ValueError("No plans supplied.")

        channels_col.update_one(
            {"channel_id": ch_id},
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
        link = f"https://t.me/{bot_username}?start={ch_id}"

        bot.send_message(
            ADMIN_ID,
            (
                "✅ <b>Setup Successful!</b>\n\n"
                "Invite Link for users:\n"
                f"<code>{esc(link)}</code>"
            ),
            parse_mode="HTML"
        )

    except Exception as e:
        bot.send_message(
            ADMIN_ID,
            (
                "❌ <b>Invalid format.</b>\n\n"
                "Use:\n"
                "<code>1:10, 1440:99, 10080:199, "
                "43200:399, 129600:799</code>"
            ),
            parse_mode="HTML"
        )
        print("Finalize channel error:", e)


# ============================================================
# PAYMENT FLOW
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("select_")
)
def user_pays(call):
    try:
        _, ch_id_raw, mins_raw = call.data.split("_")

        ch_id = int(ch_id_raw)
        mins = int(mins_raw)

        ch_data = channels_col.find_one(
            {"channel_id": ch_id}
        )

        if not ch_data:
            answer_callback(
                call,
                "❌ Channel not found.",
                show_alert=True
            )
            return

        plans = ch_data.get("plans", {})
        price = plans.get(str(mins))

        if price is None:
            answer_callback(
                call,
                "❌ Plan not found.",
                show_alert=True
            )
            return

        plan_name = format_plan(mins)

        if not UPI_ID:
            answer_callback(
                call,
                "❌ UPI is not configured.",
                show_alert=True
            )
            send_admin_error(
                "Payment configuration error",
                "UPI_ID environment variable is missing."
            )
            return

        # Properly URL-encode the entire UPI URI.
        upi_uri = (
            f"upi://pay?pa={UPI_ID}"
            f"&am={price}"
            f"&cu=INR"
        )

        qr_url = (
            "https://api.qrserver.com/v1/create-qr-code/"
            f"?size=300x300&data={quote(upi_uri, safe='')}"
        )

        markup = InlineKeyboardMarkup()

        markup.add(
            InlineKeyboardButton(
                "✅ I Have Paid",
                callback_data=f"paid_{ch_id}_{mins}"
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

        caption = (
            f"📦 Plan: <b>{esc(plan_name)}</b>\n"
            f"💰 Price: ₹{esc(price)}\n\n"
            f"UPI ID: <code>{esc(UPI_ID)}</code>\n\n"
            "Please complete the payment and click "
            "<b>I Have Paid</b>.\n\n"
            f"Admin: {esc(get_contact_username())}"
        )

        bot.send_photo(
            call.message.chat.id,
            qr_url,
            caption=caption,
            reply_markup=markup,
            parse_mode="HTML"
        )

        answer_callback(call, "✅ Payment details sent!")

    except Exception as e:
        answer_callback(
            call,
            "❌ Something went wrong!",
            show_alert=True
        )
        send_admin_error("Payment Flow Error", e)


# ============================================================
# USER PRESSES I HAVE PAID
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("paid_")
)
def admin_notify(call):
    try:
        _, ch_id_raw, mins_raw = call.data.split("_")

        ch_id = int(ch_id_raw)
        mins = int(mins_raw)
        user = call.from_user

        ch_data = channels_col.find_one(
            {"channel_id": ch_id}
        )

        if not ch_data:
            answer_callback(
                call,
                "❌ Channel not found.",
                show_alert=True
            )
            return

        price = ch_data["plans"].get(str(mins))

        if price is None:
            answer_callback(
                call,
                "❌ Plan not found.",
                show_alert=True
            )
            return

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
                    "name": user.first_name or "",
                    "username": user.username or "",
                    "plan_minutes": mins,
                    "status": "payment_pending",
                    "requested_at": time.time()
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
                callback_data=f"app_{user.id}_{ch_id}_{mins}"
            ),
            InlineKeyboardButton(
                "❌ Reject",
                callback_data=f"rej_{user.id}_{ch_id}"
            )
        )

        admin_text = (
            "🔔 <b>Payment Verification Required!</b>\n\n"
            f"👤 User: {esc(user.first_name or '')}\n"
            f"🆔 User ID: <code>{user.id}</code>\n"
            f"📢 Channel: {esc(ch_data.get('name', 'Unknown'))}\n"
            f"📦 Plan: {esc(plan_name)}\n"
            f"💰 Price: ₹{esc(price)}"
        )

        bot.send_message(
            ADMIN_ID,
            admin_text,
            reply_markup=markup,
            parse_mode="HTML"
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
            (
                "✅ Your payment request has been sent.\n\n"
                "Please wait for Admin approval.\n\n"
                f"Admin: {esc(get_contact_username())}"
            ),
            reply_markup=u_markup,
            parse_mode="HTML"
        )

        answer_callback(call, "✅ Request sent!")

    except Exception as e:
        answer_callback(
            call,
            "❌ Error!",
            show_alert=True
        )
        send_admin_error("Payment Request Error", e)


# ============================================================
# APPROVE PAYMENT
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("app_")
)
def approve_now(call):
    if call.from_user.id != ADMIN_ID:
        answer_callback(
            call,
            "⛔ Only Owner can approve payments!",
            show_alert=True
        )
        return

    try:
        _, u_id_raw, ch_id_raw, mins_raw = call.data.split("_")

        u_id = int(u_id_raw)
        ch_id = int(ch_id_raw)
        mins = int(mins_raw)

        subscription = users_col.find_one(
            {
                "user_id": u_id,
                "channel_id": ch_id
            }
        )

        if not subscription:
            answer_callback(
                call,
                "❌ User request not found!",
                show_alert=True
            )
            return

        # Make sure the requested plan is still valid.
        ch_data = channels_col.find_one(
            {"channel_id": ch_id}
        )

        if not ch_data or str(mins) not in ch_data.get("plans", {}):
            answer_callback(
                call,
                "❌ Plan no longer exists.",
                show_alert=True
            )
            return

        plan_name = format_plan(mins)

        # ====================================================
        # IMPORTANT:
        # Subscription timer does NOT start here.
        # It starts only when Telegram reports the actual join.
        # ====================================================

        users_col.update_one(
            {"_id": subscription["_id"]},
            {
                "$set": {
                    "plan_minutes": mins,
                    "status": "waiting",
                    "approved_at": time.time()
                },
                "$unset": {
                    "joined_at": "",
                    "expiry": "",
                    "invite_link": "",
                    "invite_link_expires_at": ""
                }
            }
        )

        # Invite link itself is valid for 24 hours.
        # Subscription timer still starts when user joins.
        now_timestamp = int(time.time())
        invite_expiry_timestamp = now_timestamp + (24 * 60 * 60)

        link = bot.create_chat_invite_link(
            ch_id,
            member_limit=1,
            expire_date=invite_expiry_timestamp
        )

        users_col.update_one(
            {"_id": subscription["_id"]},
            {
                "$set": {
                    "invite_link": link.invite_link,
                    "invite_link_expires_at": invite_expiry_timestamp
                }
            }
        )

        bot.send_message(
            u_id,
            (
                "🥳 <b>Payment Approved!</b>\n\n"
                f"📦 Subscription: <b>{esc(plan_name)}</b>\n\n"
                f"🔗 Join Channel:\n{esc(link.invite_link)}\n\n"
                "⚠️ Your subscription timer will start "
                "<b>when you join the channel</b>."
            ),
            parse_mode="HTML"
        )

        bot.edit_message_text(
            (
                "✅ <b>Payment Approved!</b>\n\n"
                f"👤 User ID: <code>{u_id}</code>\n"
                f"📦 Plan: <b>{esc(plan_name)}</b>\n\n"
                "⏳ Waiting for user to join...\n"
                "Timer has <b>NOT</b> started yet."
            ),
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML"
        )

        answer_callback(call, "✅ Payment approved!")

    except Exception as e:
        answer_callback(
            call,
            "❌ Approval error!",
            show_alert=True
        )
        send_admin_error("Approval Error", e)


# ============================================================
# REJECT PAYMENT
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("rej_")
)
def reject_payment(call):
    if call.from_user.id != ADMIN_ID:
        answer_callback(
            call,
            "⛔ Only Owner can reject payments!",
            show_alert=True
        )
        return

    try:
        _, u_id_raw, ch_id_raw = call.data.split("_")

        u_id = int(u_id_raw)
        ch_id = int(ch_id_raw)

        users_col.delete_one(
            {
                "user_id": u_id,
                "channel_id": ch_id,
                "status": "payment_pending"
            }
        )

        answer_callback(call, "❌ Payment rejected!")

        bot.send_message(
            u_id,
            (
                "❌ <b>Payment Request Rejected!</b>\n\n"
                "Please complete the payment and then "
                "click <b>I Have Paid</b>."
            ),
            parse_mode="HTML"
        )

        try:
            bot.edit_message_text(
                (
                    "❌ <b>Payment Rejected!</b>\n\n"
                    f"User ID: <code>{u_id}</code>\n\n"
                    "The user has been notified."
                ),
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML"
            )
        except Exception:
            pass

    except Exception as e:
        answer_callback(
            call,
            "❌ Rejection error!",
            show_alert=True
        )
        send_admin_error("Rejection Error", e)


# ============================================================
# ACTUAL CHANNEL JOIN
# ============================================================

@bot.chat_member_handler()
def track_channel_join(update):
    try:
        new_status = update.new_chat_member.status
        old_status = update.old_chat_member.status

        user = update.new_chat_member.user
        ch_id = update.chat.id

        joined_statuses = {"member", "administrator"}

        # Ignore changes where the user was already a member.
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

        joined_timestamp = time.time()
        plan_minutes = int(subscription["plan_minutes"])
        expiry_timestamp = joined_timestamp + (plan_minutes * 60)

        users_col.update_one(
            {"_id": subscription["_id"]},
            {
                "$set": {
                    "joined_at": joined_timestamp,
                    "expiry": expiry_timestamp,
                    "status": "active",
                    "name": user.first_name or "",
                    "username": user.username or ""
                }
            }
        )

        # Revoke the one-time invite after successful join.
        invite_link = subscription.get("invite_link")

        if invite_link:
            try:
                bot.revoke_chat_invite_link(
                    ch_id,
                    invite_link
                )
            except Exception:
                pass

        plan_name = format_plan(plan_minutes)

        admin_joined_text = format_ist_time(joined_timestamp)
        admin_expiry_text = format_ist_time(expiry_timestamp)

        user_timezone = get_user_timezone(user.id) or IST

        user_joined_text = format_time(
            joined_timestamp,
            user_timezone
        )

        user_expiry_text = format_time(
            expiry_timestamp,
            user_timezone
        )

        bot.send_message(
            ADMIN_ID,
            (
                "👤 <b>User Joined!</b>\n\n"
                f"User: {esc(user.first_name or '')}\n"
                f"User ID: <code>{user.id}</code>\n"
                f"Channel ID: <code>{ch_id}</code>\n\n"
                f"📥 Joined:\n{esc(admin_joined_text)} IST\n\n"
                f"📦 Subscription:\n{esc(plan_name)}\n\n"
                f"🔴 Expires:\n{esc(admin_expiry_text)} IST"
            ),
            parse_mode="HTML"
        )

        timezone_name = getattr(
            user_timezone,
            "key",
            "Asia/Kolkata"
        )

        bot.send_message(
            user.id,
            (
                "✅ <b>Subscription Started!</b>\n\n"
                "Your subscription has started now.\n\n"
                f"📦 Duration: <b>{esc(plan_name)}</b>\n\n"
                f"📥 Joined:\n{esc(user_joined_text)}\n\n"
                f"🔴 Expires at:\n{esc(user_expiry_text)}\n\n"
                f"🌍 Timezone: <code>{esc(timezone_name)}</code>"
            ),
            parse_mode="HTML"
        )

    except Exception as e:
        send_admin_error("Join Tracking Error", e)


# ============================================================
# /USERS
# ============================================================

@bot.message_handler(
    commands=["users"],
    func=lambda m: m.from_user.id == ADMIN_ID
)
def show_users(message):
    """Show only real subscription records.

    /users intentionally excludes payment_pending, rejected/expired records,
    timezone-only profiles, and any other unrelated MongoDB documents.
    Only users currently waiting to join or actively subscribed are shown.
    """
    try:
        users = list(
            users_col.find(
                {
                    "channel_id": {"$exists": True},
                    "status": {"$in": ["waiting", "active"]}
                }
            ).sort("joined_at", 1)
        )

        if not users:
            bot.send_message(
                ADMIN_ID,
                "👥 <b>Subscribers</b>\n\nNo active or waiting subscribers.",
                parse_mode="HTML"
            )
            return

        now = time.time()
        blocks = []

        for index, user in enumerate(users, 1):
            status = user.get("status")
            user_id = user.get("user_id", "Unknown")
            channel_id = user.get("channel_id", "Unknown")
            name = esc(str(user.get("name") or "Unknown"))

            if status == "waiting":
                blocks.append(
                    (
                        f"{index}. 👤 <b>{name}</b>\n"
                        f"🆔 ID: <code>{esc(str(user_id))}</code>\n"
                        f"📢 Channel: <code>{esc(str(channel_id))}</code>\n"
                        "🟡 Status: Waiting to join\n"
                        f"📦 Plan: <b>{esc(format_plan(int(user.get('plan_minutes', 0))))}</b>\n"
                        "⏳ Timer: Not started yet\n"
                    )
                )
                continue

            joined_ts = user.get("joined_at")
            expiry_ts = user.get("expiry")

            if not expiry_ts:
                remaining = "Unknown"
            else:
                remaining = format_remaining(int(float(expiry_ts) - now))

            blocks.append(
                (
                    f"{index}. 👤 <b>{name}</b>\n"
                    f"🆔 ID: <code>{esc(str(user_id))}</code>\n"
                    f"📢 Channel: <code>{esc(str(channel_id))}</code>\n"
                    "🟢 Status: Active\n"
                    f"📦 Plan: <b>{esc(format_plan(int(user.get('plan_minutes', 0))))}</b>\n"
                    f"📥 Joined: {esc(format_ist_time(joined_ts))} IST\n"
                    f"🔴 Expires: {esc(format_ist_time(expiry_ts))} IST\n"
                    f"⏳ Remaining: {esc(remaining)}\n"
                )
            )

        current = "👥 <b>SUBSCRIBERS</b>\n\n"

        for block in blocks:
            if len(current) + len(block) + 2 > 3800:
                bot.send_message(ADMIN_ID, current, parse_mode="HTML")
                current = block + "\n"
            else:
                current += block + "\n"

        if current.strip():
            bot.send_message(ADMIN_ID, current, parse_mode="HTML")

    except Exception as e:
        print("Users command error:", e)
        send_admin_error("Users command error", e)


# ============================================================
# MANAGE CHANNEL
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("manage_")
)
def manage_ch(call):
    if call.from_user.id != ADMIN_ID:
        answer_callback(
            call,
            "⛔ Only Owner can manage channels!",
            show_alert=True
        )
        return

    try:
        ch_id = int(call.data.split("_")[1])

        ch_data = channels_col.find_one(
            {"channel_id": ch_id}
        )

        if not ch_data:
            answer_callback(
                call,
                "❌ Channel not found!",
                show_alert=True
            )
            return

        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start={ch_id}"

        bot.edit_message_text(
            (
                f"⚙️ Settings for: <b>{esc(ch_data.get('name', 'Channel'))}</b>\n\n"
                f"Your Link:\n<code>{esc(link)}</code>\n\n"
                "To edit prices, use /add and "
                "forward a message from this channel again."
            ),
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML"
        )

        answer_callback(call)

    except Exception as e:
        answer_callback(
            call,
            "❌ Error!",
            show_alert=True
        )
        send_admin_error("Manage channel error", e)


# ============================================================
# EXPIRED USERS
#
# IMPORTANT:
# 1. Ban/remove user.
# 2. Immediately unban.
# 3. User is NOT permanently banned.
# 4. Delete old subscription.
# 5. User can open the bot again and buy a new plan.
# ============================================================

def _get_bot_channel_permissions(channel_id):
    """Return the bot's member object in the channel, or None on error."""
    try:
        me = bot.get_me()
        return bot.get_chat_member(channel_id, me.id)
    except Exception as e:
        print(f"❌ Could not inspect bot permissions | channel={channel_id}: {e}")
        return None


def _remove_user_and_make_rejoinable(channel_id, user_id):
    """
    Remove a user from the channel WITHOUT leaving them permanently banned.

    Telegram's unbanChatMember method, when called with only_if_banned=False,
    guarantees that the user is not a member after the call and can join again
    through an invite link. If the user is currently a member, Telegram removes
    them as part of this call. This is safer than ban -> unban because there is
    no race between two API calls.
    """

    # First try the one-call kick/unban operation.
    result = bot.unban_chat_member(
        channel_id,
        user_id,
        only_if_banned=False
    )

    if not result:
        raise RuntimeError("Telegram returned False while removing/unbanning user")

    # Verify Telegram now sees the user as left or banned-free.
    # We retry briefly because Telegram/member-state propagation can take a moment.
    last_status = None

    for _ in range(4):
        try:
            member = bot.get_chat_member(channel_id, user_id)
            last_status = member.status

            if member.status in ("left", "kicked"):
                return True

            # If Telegram reports a banned member, explicitly unban once.
            if member.status == "banned":
                bot.unban_chat_member(
                    channel_id,
                    user_id,
                    only_if_banned=True
                )
        except Exception:
            # getChatMember can be unavailable for some channel/member states;
            # the successful unban call above is still authoritative.
            return True

        time.sleep(0.75)

    # If it is still a member after successful unban, do one final unconditional
    # unban. This also removes a member when only_if_banned is False.
    if last_status not in ("left", "kicked", None):
        bot.unban_chat_member(
            channel_id,
            user_id,
            only_if_banned=False
        )

    return True


def _notify_expired_user(user_id, channel_id):
    """Send the renewal message. Notification failure must not block cleanup."""
    try:
        bot_username = bot.get_me().username
        rejoin_url = f"https://t.me/{bot_username}?start={channel_id}"

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton(
                "🔄 Re-join / Renew",
                url=rejoin_url
            )
        )

        bot.send_message(
            user_id,
            (
                "⏰ <b>Subscription Expired!</b>\n\n"
                "Your premium subscription has expired and your "
                "channel access has been removed.\n\n"
                "You are <b>not permanently banned</b>.\n\n"
                "Click below to renew and receive a fresh join link:"
            ),
            reply_markup=markup,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"⚠️ Expiry notification failed | user={user_id}: {e}")


def kick_expired_users():
    """
    Expire subscriptions quickly and safely.

    The checker runs every few seconds instead of every minute. We do NOT use
    ban -> unban anymore. Telegram's unbanChatMember with only_if_banned=False
    itself removes a current member and leaves them eligible to rejoin.

    A failed Telegram operation is NOT deleted from MongoDB. It is marked as
    expiry_pending and retried on the next scheduler pass.
    """
    now = int(time.time())

    # Process both normal expired subscriptions and previous failed cleanups.
    expired_users = users_col.find(
        {
            "status": {"$in": ["active", "expiry_pending"]},
            "expiry": {"$lte": now}
        }
    )

    for user in expired_users:
        try:
            user_id = int(user["user_id"])
            channel_id = int(user["channel_id"])

            # Atomically claim this record so two scheduler runs/processes do
            # not try to remove the same user at the same time.
            claimed = users_col.update_one(
                {
                    "_id": user["_id"],
                    "status": {"$in": ["active", "expiry_pending"]}
                },
                {
                    "$set": {
                        "status": "expiry_pending",
                        "expiry_processing_at": time.time()
                    }
                }
            )

            if claimed.modified_count == 0 and user.get("status") != "expiry_pending":
                continue

            # Check that the bot really has the required admin privilege.
            # If this is missing, keeping the DB record allows automatic retry
            # after the admin permission is fixed.
            bot_member = _get_bot_channel_permissions(channel_id)

            if bot_member is not None:
                if bot_member.status != "administrator":
                    raise RuntimeError(
                        f"Bot is not administrator in channel {channel_id} "
                        f"(status={bot_member.status})"
                    )

                if not getattr(bot_member, "can_restrict_members", False):
                    raise RuntimeError(
                        f"Bot lacks 'Restrict/Ban users' permission in channel {channel_id}"
                    )

            # THIS is the important fix:
            # one Telegram API call removes the member and makes them rejoinable.
            _remove_user_and_make_rejoinable(channel_id, user_id)

            print(
                f"✅ Expired user kicked + unbanned | "
                f"user={user_id} channel={channel_id}"
            )

            # Notify user after successful removal/unban.
            _notify_expired_user(user_id, channel_id)

            # Only now delete the old subscription.
            users_col.delete_one({"_id": user["_id"]})

        except Exception as e:
            print(
                f"❌ Expiry cleanup failed | "
                f"user={user.get('user_id')} channel={user.get('channel_id')}: {e}"
            )

            # Keep the record for retry instead of losing the subscription.
            try:
                users_col.update_one(
                    {"_id": user["_id"]},
                    {
                        "$set": {
                            "status": "expiry_pending",
                            "expiry_cleanup_error": str(e)[:1000],
                            "expiry_last_attempt_at": time.time()
                        }
                    }
                )
            except Exception as db_error:
                print(f"❌ Could not save expiry retry state: {db_error}")

            send_admin_error(
                "Expiry cleanup failed",
                f"User: {user.get('user_id')}\n"
                f"Channel: {user.get('channel_id')}\n"
                f"Error: {e}"
            )


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":
    keep_alive()

    scheduler = BackgroundScheduler()

    # Run once immediately on startup so expired users are not left waiting
    # for the first scheduler tick.
    try:
        kick_expired_users()
    except Exception as e:
        print(f"Initial expiry check failed: {e}")

    scheduler.add_job(
        kick_expired_users,
        "interval",
        seconds=10,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
        id="expiry_checker",
        replace_existing=True
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
