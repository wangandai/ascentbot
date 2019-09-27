import telebot
from telebot import types
import models as m
import datetime
import threading
import time
from custom_errors import *
import os
import logging
import pytz
from flask import Flask, request
from dotenv import load_dotenv
load_dotenv()

__tz__ = pytz.timezone("Asia/Singapore")
__token__ = os.getenv("TG_TOKEN")
telebot.logger.setLevel(logging.INFO)
bot = telebot.AsyncTeleBot(__token__)

guilds = m.Guilds.load()


################################
#       Renderers              #
################################
def render_adv_text():
    return """
Advanced commands:
Register with alt:
/exped reg <team> <alt>
Create new expedition
/exped new <team> <HHMM> <description>
Delete expedition
/exped delete <team>
"""


def render_expedition(expedition):
    msg = "⚔️ {}    🕑 {}    👥 {}\n".format(expedition.title,
                                             datetime.time.strftime(expedition.time, "%H%M"),
                                             len(expedition.members))
    if len(expedition.description) > 0:
        msg += "📋 {}\n".format(expedition.description)
    for i, member in enumerate(expedition.members):
        msg += "{}. [{}](tg://user?id={}) {}\n".format(i + 1, member.tg_handle, member.tg_id,
                                                       member.label if member.label is not None else "")
    return msg + "\n"


def render_expeditions(guild):
    msg = ""
    expeds = list(guild.expeditions.values())
    expeds.sort(key=lambda x: x.time)
    for e in expeds:
        msg += render_expedition(e)
    if len(expeds) is 0:
        msg += "No expeditions"
    return msg


def render_guild_admin(guild):
    current_day = datetime.datetime.now().date()
    guild_msg = "Guild Admin {}/{}\n\n".format(current_day.month, current_day.day)
    guild_msg += render_expeditions(guild)
    guild_msg += "\n"
    guild_msg += render_adv_text()
    return guild_msg


def render_poll_markup(guild):
    markup = types.InlineKeyboardMarkup()
    # Render exped polls
    expeds = list(guild.expeditions.values())
    expeds.sort(key=lambda x: x.time)
    for e in expeds:
        markup.add(types.InlineKeyboardButton(e.title, callback_data="/exped reg {}".format(e.title)))
    return markup


################################
#       Middleware             #
################################
def _update_pinned_msg(guild):
    if guild.pinned_message_id is not None:
        bot.edit_message_text(render_guild_admin(guild),
                              chat_id=guild.chat_id,
                              message_id=guild.pinned_message_id,
                              parse_mode="Markdown",
                              reply_markup=render_poll_markup(guild))


def process_command(commands, message, doc):
    try:
        guild = guilds.get(message.chat.id)
        parts = message.text.split(' ')
        if len(parts) >= 2 and parts[1] in commands:
            command_str = parts[1]
            answer_text = commands[command_str](message)
            _update_pinned_msg(guild)
            guilds.save()
        else:
            raise WrongCommandError(doc)
    except Exception as e:
        if issubclass(type(e), GuildError):
            answer_text = e.message
        else:
            logging.error(e)
            answer_text = "Unknown error"
    return answer_text


def handle_command(commands, message, doc):
    answer_text = process_command(commands, message, doc)
    bot.send_message(message.chat.id, answer_text, parse_mode="Markdown")


def handle_callback(commands, call):
    # monkey patch message data to format of text commands
    call.message.text = call.data
    call.message.from_user = call.from_user
    answer_text = process_command(commands, call.message, "Command received: {}".format(call.data))
    bot.answer_callback_query(call.id, text=answer_text)


################################
#       Callback Handlers      #
################################
@bot.callback_query_handler(func=lambda c: True)
def cb_query_handler(call):
    cb_handlers = {
        'reg': exped_reg,
    }
    handle_callback(cb_handlers, call)


################################
#       Expedition Handlers    #
################################
def exped_new(message):
    doc = """
/exped new team1 1500
/exped new team1 1500 description
    """
    parts = message.text.split(' ', 4)
    if len(parts) not in [4, 5]:
        raise WrongCommandError(doc)
    time = parts[3]
    title = parts[2]
    try:
        description = parts[4]
    except IndexError:
        description = ""

    try:
        guild = guilds.get(message.chat.id)
        e = guild.new_expedition(title, time, description)
        return "Expedition created: {} {}".format(e.title, time)
    except ValueError:
        raise WrongCommandError(doc)


def exped_time(message):
    doc = """
/exped time team HHMM
        """
    parts = message.text.split(' ')
    if len(parts) != 4:
        raise WrongCommandError(doc)
    try:
        guild = guilds.get(message.chat.id)
        e = guild.set_expedition_time(parts[2], parts[3])
        return "{} updated to {}".format(e.title, parts[3])
    except ValueError:
        raise WrongCommandError(doc)


def exped_delete(message):
    doc = """
/exped delete tea
    """
    parts = message.text.split(' ')
    if len(parts) == 3:
        guild = guilds.get(message.chat.id)
        guild.delete_expedition(parts[2])
        return "{} deleted.".format(parts[2])
    else:
        raise WrongCommandError(doc)


def exped_reg(message):
    doc = """
/exped reg team
/exped reg team [label]
        """
    parts = message.text.split(' ')
    if len(parts) == 4:
        label = parts[3]
    elif len(parts) == 3:
        label = ""
    else:
        raise WrongCommandError(doc)

    title = parts[2]
    handle = message.from_user.first_name
    handle_id = message.from_user.id
    guild = guilds.get(message.chat.id)

    try:
        e, member = guild.checkin_expedition(title, handle_id, handle, label)
        return "{} checked in to {}".format(member.tg_handle, e.title)
    except ExpedMemberAlreadyExists:
        e, member = guild.checkout_expedition(title, handle_id, handle, label)
        return "{} checked out of {}".format(member.tg_handle, e.title)


def exped_view(message):
    doc = """Possible messages:
/exped view
    """
    guild = guilds.get(message.chat.id)
    return render_expeditions(guild)


@bot.edited_message_handler(commands=['exped'])
@bot.message_handler(commands=['exped'])
def exped(message):
    exped_commands = {
        'reg': exped_reg,
        'new': exped_new,
        'delete': exped_delete,
        'time': exped_time,
        'view': exped_view
    }
    doc = """
/exped command [arguments...]
Available commands are : {}
    """.format([a for a in exped_commands.keys()])
    handle_command(exped_commands, message, doc)


################################
#       Admin Handlers         #
################################
def _guild_pin(chat_id):
    guild = guilds.get(chat_id)
    guild_msg = render_guild_admin(guild)
    sent = bot.send_message(guild.chat_id,
                            guild_msg,
                            parse_mode="Markdown",
                            reply_markup=render_poll_markup(guild)).wait()
    guild.pinned_message_id = sent.message_id
    bot.pin_chat_message(guild.chat_id, guild.pinned_message_id)


def guild_pin(message):
    _guild_pin(message.chat.id)


@bot.edited_message_handler(commands=['admin'])
@bot.message_handler(commands=['admin'])
def admin(message):
    admin_commands = {
        "pin": guild_pin,
    }
    doc = """
/admin command [arguments...]
Available commands are : {}
    """.format([a for a in admin_commands.keys()])
    handle_command(admin_commands, message, doc)


@bot.message_handler(commands=['start'])
def start(message):
    try:
        guilds.get(message.chat.id)
        bot.send_message(message.chat.id, "Guild bot ready.")
    except GuildNotFoundError:
        guild = m.Guild()
        guilds.set(message.chat.id, guild)
        guild.chat_id = message.chat.id
        guild.title = message.chat.title
        guilds.save()
        bot.send_message(message.chat.id, "Guild bot initialized.")


@bot.message_handler(commands=['reset_guild'])
def reset(message):
    guilds.guilds.pop(message.chat.id, None)
    start(message)


def get_singapore_time_now():
    now = datetime.datetime.utcnow()
    offset = __tz__.utcoffset(now)
    return now + offset


def equal_hour_minute(time1, time2):
    return time1.hour == time2.hour and time1.minute == time2.minute


class GuildAutomation(object):
    def __init__(self):
        thread_exped = threading.Thread(target=self.exped_reminder, args=())
        thread_exped.daemon = True
        thread_exped.start()

        thread_reset = threading.Thread(target=self.daily_reset, args=())
        thread_reset.daemon = True
        thread_reset.start()

    def exped_reminder(self):
        while True:
            now = get_singapore_time_now()
            two_mins = now + datetime.timedelta(minutes=2)
            for guild in guilds.values():
                for e in guild.expeditions.values():
                    if equal_hour_minute(e.time, two_mins):
                        bot.send_message(guild.chat_id,
                                         "Expedition Reminder:\n{}".format(render_expedition(e)),
                                         parse_mode="Markdown")
            time.sleep(60)

    def daily_reset(self):
        while True:
            now = get_singapore_time_now()
            for guild in guilds.values():
                if now.hour == guild.daily_reset_time:
                    guild.reset_expeditions()
                    _guild_pin(guild.chat_id)
            guilds.save()
            time.sleep(60 * 60)


GuildAutomation()


if __name__ == "__main__":

    if os.getenv("LISTEN_MODE") == "webhook":
        server = Flask(__name__)

        @server.route('/' + __token__, methods=['POST'])
        def getMessage():
            bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
            return "!", 200


        @server.route("/")
        def webhook():
            bot.remove_webhook()
            bot.set_webhook(url="{}/{}".format(os.environ.get('WEBHOOK_HOST', 'localhost:5000'), __token__))
            return "!", 200


        server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))

    else:
        bot.remove_webhook()
        bot.polling(none_stop=True)
