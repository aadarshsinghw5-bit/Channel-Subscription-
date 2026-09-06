import os
import telebot

from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from pymongo import MongoClient

from datetime import datetime, timedelta

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


bot = telebot.TeleBot(BOT_TOKEN)


# ============================================================
# MONGODB
# ============================================================

client = MongoClient(MONGO_URI)

db = client["sub_management"]

channels_col = db["channels"]
users_col = db["users"]


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


# ============================================================
# START
# ============================================================

@bot.message_handler(commands=["start"])
def start_handler(message):

    user_id = message.from_user.id

    text = (message.text or "").split()


    # --------------------------------------------------------
    # USER ENTRY THROUGH DEEP LINK
    # --------------------------------------------------------

    if len(text) > 1:

        try:

            ch_id = int(text[1])

            ch_data = channels_col.find_one(
                {
                    "channel_id": ch_id
                }
            )

            if ch_data:

                markup = InlineKeyboardMarkup()


                # --------------------------------------------
                # DISPLAY PLANS
                # --------------------------------------------

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

                    message.chat.id,

                    f"Welcome!\n\n"
                    f"You are joining: "
                    f"*{ch_data['name']}*.\n\n"
                    f"Please select a subscription plan below:",

                    reply_markup=markup,

                    parse_mode="Markdown"
                )

                return

        except Exception:
            pass


    # --------------------------------------------------------
    # ADMIN PANEL
    # --------------------------------------------------------

    if user_id == ADMIN_ID:

        bot.send_message(

            message.chat.id,

            "✅ *Admin Panel Active!*\n\n"

            "/add - Add/Edit Channel & Prices\n"
            "/channels - Manage Existing Channels\n"
            "/users - View Subscribers",

            parse_mode="Markdown"
        )

    else:

        bot.send_message(

            message.chat.id,

            "Welcome!\n\n"
            "To join a channel, please use the link "
            "provided by the Admin."
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


        # Save/update pending payment

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

                    "requested_at": datetime.now().timestamp()

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

                callback_data=f"rej_{user.id}_{ch_id}"
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

    # OWNER CHECK

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


        # ----------------------------------------------------
        # IMPORTANT:
        # Subscription timer DOES NOT start here.
        # ----------------------------------------------------

        users_col.update_one(

            {
                "_id": subscription["_id"]
            },

            {
                "$set": {

                    "plan_minutes": mins,

                    "status": "waiting",

                    "approved_at": datetime.now().timestamp()

                },

                "$unset": {

                    "joined_at": "",

                    "expiry": "",

                    "invite_link": ""

                }
            }
        )


        # Invite has no subscription expiry.
        # Timer will start when user actually joins.

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

                    "invite_link": link.invite_link

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

    # OWNER CHECK

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


        # Remove pending request

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


        # Notify user

        bot.send_message(

            u_id,

            "❌ *Payment Request Rejected!*\n\n"

            "Please complete the payment and then "
            "click *I Have Paid*.",

            parse_mode="Markdown"
        )


        # Notify owner

        bot.send_message(

            ADMIN_ID,

            f"❌ *Request Rejected!*\n\n"

            f"User ID: `{u_id}`\n\n"

            "The user has been notified.",

            parse_mode="Markdown"
        )


        # Update owner message

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


        # User already was a member

        if (

            new_status in joined_statuses

            and old_status in joined_statuses

        ):

            return


        # User must have newly joined

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


        users_col.update_one(

            {
                "_id": subscription["_id"]
            },

            {
                "$set": {

                    "joined_at":
                        joined_at.timestamp(),

                    "expiry":
                        expiry_datetime.timestamp(),

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
        # OWNER NOTIFICATION
        # ----------------------------------------------------

        bot.send_message(

            ADMIN_ID,

            f"👤 *User Joined!*\n\n"

            f"User: {user.first_name}\n"
            f"User ID: `{user.id}`\n"
            f"Channel ID: `{ch_id}`\n\n"

            f"📥 Joined:\n"
            f"{joined_at.strftime('%d %b %Y, %I:%M %p')}\n\n"

            f"📦 Subscription:\n"
            f"{plan_name}\n\n"

            f"🔴 Expires:\n"
            f"{expiry_datetime.strftime('%d %b %Y, %I:%M %p')}",

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
            f"{joined_at.strftime('%d %b %Y, %I:%M %p')}\n\n"

            f"🔴 Expires at:\n"
            f"{expiry_datetime.strftime('%d %b %Y, %I:%M %p')}",

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


        # Don't show payment requests
        # in subscriber list

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


        # ----------------------------------------------------
        # WAITING
        # ----------------------------------------------------

        if status == "waiting":

            text += (

                f"{index}. 👤 *{name}*\n"

                f"🆔 ID: `{user_id}`\n"

                f"📢 Channel: `{channel_id}`\n"

                f"🟡 Status: Waiting to join\n"

                f"⏳ Timer: Not started yet\n\n"

            )

            continue


        # ----------------------------------------------------
        # ACTIVE
        # ----------------------------------------------------

        if status == "active":

            joined_ts = user.get(
                "joined_at"
            )

            expiry_ts = user.get(
                "expiry"
            )


            if joined_ts:

                joined_text = (

                    datetime.fromtimestamp(
                        joined_ts
                    ).strftime(
                        "%d %b %Y, %I:%M %p"
                    )
                )

            else:

                joined_text = "Unknown"


            if expiry_ts:

                expiry_text = (

                    datetime.fromtimestamp(
                        expiry_ts
                    ).strftime(
                        "%d %b %Y, %I:%M %p"
                    )
                )


                remaining_seconds = int(

                    expiry_ts - now

                )


                remaining = format_remaining(

                    remaining_seconds

                )

            else:

                expiry_text = "Unknown"

                remaining = "Unknown"


            text += (

                f"{index}. 👤 *{name}*\n"

                f"🆔 ID: `{user_id}`\n"

                f"📢 Channel: `{channel_id}`\n"

                f"🟢 Status: Active\n"

                f"📥 Joined: {joined_text}\n"

                f"🔴 Expires: {expiry_text}\n"

                f"⏳ Remaining: {remaining}\n\n"

            )

            continue


        # ----------------------------------------------------
        # OTHER
        # ----------------------------------------------------

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


    # Telegram message limit

    if len(text) <= 4000:

        bot.send_message(

            ADMIN_ID,

            text,

            parse_mode="Markdown"
        )

    else:

        for i in range(
            0,
            len(text),
            4000
        ):

            bot.send_message(

                ADMIN_ID,

                text[i:i + 4000],

                parse_mode="Markdown"
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


    except Exception as e:

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
            # REMOVE USER FROM CHANNEL
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
            # DELETE ACTIVE SUBSCRIPTION
            # ------------------------------------------------

            users_col.delete_one(

                {
                    "_id": user["_id"]
                }
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
