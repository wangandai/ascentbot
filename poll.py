import telebot
from telebot import types
import models as m
import datetime as dt
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
                                             render_human_time(expedition.get_time()),
                                             len(expedition.members))
    if len(expedition.description) > 0:
        msg += "📋 {}\n".format(expedition.description)
    for i, member in enumerate(expedition.members):
        msg += "{}. [{}](tg://user?id={}) {}\n".format(i + 1, member.tg_handle, member.tg_id,
                                                       member.label if member.label is not None else "")
    return msg + "\n"


def sort_expeditions(expeds, daily_reset_time=0):
    return sorted(expeds, key=lambda x: time_shifted_back_hours(x.get_time(), daily_reset_time))


def filter_expeditions(expeds, daily_reset_time=0):
    now = get_singapore_time_now()
    if 0 <= now.time().hour - daily_reset_time <= 2:  # if current time is within 2 hours after daily reset time, dont filter
        return expeds
    two_h_before = (now - dt.timedelta(hours=2)).time()
    offset = daily_reset_time
    expeds = [e for e in expeds if
              time_shifted_back_hours(e.get_time(), offset) > time_shifted_back_hours(two_h_before, offset)]
    return expeds


def render_expeditions(expeds, guild_reset_time=0, sort=True, filter=True):
    msg = ""
    if sort:
        expeds = sort_expeditions(expeds, guild_reset_time)
    if filter:
        expeds = filter_expeditions(expeds, guild_reset_time)
    for e in expeds:
        msg += render_expedition(e)
    if len(expeds) is 0:
        msg += "No expeditions"
    return msg


def render_guild_admin(guild):
    current_day = dt.datetime.now().date()
    expeds = list(guild.expeditions.values())
    guild_msg = "Guild Admin {}/{}\n\n".format(current_day.month, current_day.day)
    guild_msg += render_expeditions(expeds, guild_reset_time=guild.daily_reset_time)
    guild_msg += "\n"
    guild_msg += render_adv_text()
    return guild_msg


def render_poll_markup(guild):
    markup = types.InlineKeyboardMarkup()
    expeds = list(guild.expeditions.values())
    expeds = sort_expeditions(expeds, guild.daily_reset_time)
    expeds = filter_expeditions(expeds, guild.daily_reset_time)
    for e in expeds:
        markup.add(types.InlineKeyboardButton("Join {} ({})".format(e.title, render_human_time(e.get_time())),
                                              callback_data="/exped reg {}".format(e.title)))
    # Render fort attendance poll
    fort_mark_button = types.InlineKeyboardButton("Went fort today",
                                                  callback_data="/fort mark")
    fort_check_button = types.InlineKeyboardButton("My fort count",
                                                   callback_data="/fort check")
    markup.row(fort_mark_button, fort_check_button)
    return markup


def render_human_time(time_obj):
    if time_obj.minute > 0:
        return time_obj.strftime("%I.%M%p").lstrip("0").lower()
    else:
        return time_obj.strftime("%I%p").lstrip("0").lower()


def time_shifted_back_hours(t, hour_offset):
    new_hour = t.hour - hour_offset
    if new_hour < 0:
        new_hour = 24 + new_hour
    return t.replace(hour=new_hour)


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
            answer = commands[command_str](message)
            _update_pinned_msg(guild)
            guilds.save()
        else:
            raise WrongCommandError(doc)
    except Exception as e:
        if issubclass(type(e), GuildError):
            answer = m.MessageReply(e.message)
        else:
            logging.exception(e)
            answer = m.MessageReply("Unknown error")
    return answer


def handle_command(commands, message, doc):
    answer = process_command(commands, message, doc)
    if answer is not None and len(answer.message) > 0:
        sent = (bot.send_message(message.chat.id, answer.message,
                                 parse_mode="Markdown",
                                 disable_notification=True
                                 )).wait()
        if answer.temporary:
            delete_command_and_reply(message, sent)


def handle_callback(commands, call):
    # monkey patch message data to format of text commands
    call.message.text = call.data
    call.message.from_user = call.from_user
    answer = process_command(commands, call.message, "Command received: {}".format(call.data))
    bot.answer_callback_query(call.id, text=answer.message)


def delete_command_and_reply(message, reply):
    def _delete_messages(msg, rep):
        if type(rep) is tuple:
            logging.error("Could not delete reply: {}".format(reply[1]))
            return
        time.sleep(5)
        bot.delete_message(msg.chat.id, msg.message_id)
        bot.delete_message(msg.chat.id, reply.message_id)
    del_task = threading.Thread(target=_delete_messages, args=(message, reply), daemon=True)
    del_task.start()


################################
#       Callback Handlers      #
################################
@bot.callback_query_handler(func=lambda c: True)
def cb_query_handler(call):
    cb_handlers = {
        'reg': exped_reg,
        'mark': fort_mark,
        'check': fort_check,
        'ready': exped_ready,
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
        return m.MessageReply("Expedition created: {} {}".format(e.title, time))
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
        return m.MessageReply("{} updated to {}".format(e.title, parts[3]))
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
        return m.MessageReply("{} deleted.".format(parts[2]))
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
        answer_text = "{} checked in to {}".format(member.tg_handle, e.title)
    except ExpedMemberAlreadyExists:
        e, member = guild.checkout_expedition(title, handle_id, handle, label)
        answer_text = "{} checked out of {}".format(member.tg_handle, e.title)
    return m.MessageReply(answer_text)


def exped_view(message):
    doc = """Possible messages:
/exped view
    """
    guild = guilds.get(message.chat.id)
    expeds = list(guild.expeditions.values())
    return m.MessageReply(render_expeditions(expeds,
                                             guild_reset_time=guild.daily_reset_time,
                                             filter=False),
                          temporary=False)

def exped_ready(message):
    doc = """
This handles a callback from an expedition reminder, when a user pressed the I'm ready button.
    """
    print(message.text)
    return m.MessageReply("You are ready!")


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
#       Fort Handlers          #
################################
def fort_mark(message):
    doc = """Possible messages:
/fort mark
/fort mark <alt>
"""
    parts = message.text.split(' ')
    if len(parts) == 3:
        label = parts[2]
    elif len(parts) == 2:
        label = ""
    else:
        raise WrongCommandError(doc)

    guild = guilds.get(message.chat.id)
    handle = message.from_user.first_name
    handle_id = message.from_user.id

    try:
        guild.fort_mark(handle_id, handle, label)
        answer_text = "Attendance added for {}".format(handle)
    except FortAttendanceExistsError:
        guild.fort_unmark(handle_id, handle, label)
        answer_text = "Attendance removed for {}".format(handle)
    return m.MessageReply(answer_text)


def fort_check(message):
    doc = """Possible messages:
/fort check
/fort check <alt>
    """
    parts = message.text.split(' ')
    if len(parts) == 3:
        label = parts[2]
    elif len(parts) == 2:
        label = ""
    else:
        raise WrongCommandError(doc)

    guild = guilds.get(message.chat.id)
    handle = message.from_user.first_name
    handle_id = message.from_user.id

    today = int(guild.get_attendance_today(handle_id, handle, label))
    try:
        result = guild.get_history_of(handle_id, handle, label)
    except FortAttendanceNotFoundError:
        result = 0
    return m.MessageReply("Fort count for {}: {}".format(handle, result + today))


def fort_reset_history(message):
    doc = """Possible messages:
/fort reset_history
    """
    guild = guilds.get(message.chat.id)
    guild.reset_fort_history()
    guilds.save()
    return m.MessageReply("Fort history reset.", temporary=False)


def fort_get_history(message):
    doc = """Possible messages:
/fort get_history
    """
    guild = guilds.get(message.chat.id)
    history = guild.get_history_all()
    current_day = dt.datetime.now().date()
    msg = "*Fort history {}/{}*\n".format(current_day.month, current_day.day)
    for p in history:
        msg += "{} : {}\n".format(p.tg_handle, history[p])
    msg += "\nIf your name is not here, your recorded count is 0."
    return m.MessageReply(msg, temporary=False)


@bot.edited_message_handler(commands=['fort'])
@bot.message_handler(commands=['fort'])
def fort(message):
    fort_commands = {
        'mark': fort_mark,
        'check': fort_check,
        'reset_history': fort_reset_history,
        'get_history': fort_get_history,
    }
    doc = """
/fort command [arguments...]
Available commands are : {}
    """.format([a for a in fort_commands.keys()])
    handle_command(fort_commands, message, doc)


################################
#       Admin Handlers         #
################################
def _guild_pin(chat_id):
    guild = guilds.get(chat_id)
    guild_msg = render_guild_admin(guild)
    sent = bot.send_message(guild.chat_id,
                            guild_msg,
                            parse_mode="Markdown",
                            reply_markup=render_poll_markup(guild),
                            disable_notification=True).wait()

    if type(sent) is tuple:
        if "blocked" in sent[1].result.text:
            _guild_stop(chat_id)
    else:
        guild.pinned_message_id = sent.message_id
        bot.pin_chat_message(guild.chat_id, guild.pinned_message_id)
    return None


def guild_pin(message):
    return _guild_pin(message.chat.id)


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


def _guild_stop(chat_id):
    g = guilds.get(chat_id)
    setattr(g, "stopped", True)


@bot.message_handler(commands=['stop'])
def stop(message):
    try:
        _guild_stop(message.chat.id)
        bot.send_message(message.chat.id, "Guild bot stopped.")
        guilds.save()
    except GuildNotFoundError:
        bot.send_message(message.chat.id, "Guild bot already stopped.")


@bot.message_handler(commands=['start'])
def start(message):
    try:
        g = guilds.get(message.chat.id, ignore_stopped=True)
        setattr(g, "stopped", False)
        bot.send_message(message.chat.id, "Guild bot ready.")
    except GuildNotFoundError:
        guild = m.Guild()
        guilds.set(message.chat.id, guild)
        guild.chat_id = message.chat.id
        guild.title = message.chat.title
        bot.send_message(message.chat.id, "Guild bot initialized.")
    finally:
        guilds.save()


@bot.message_handler(commands=['reset_guild'])
def reset(message):
    guilds.guilds.pop(message.chat.id, None)
    start(message)


def get_singapore_time_now():
    now = dt.datetime.utcnow()
    offset = __tz__.utcoffset(now)
    return now + offset


def equal_hour_minute(time1, time2):
    return time1.hour == time2.hour and time1.minute == time2.minute


class GuildAutomation(object):
    def __init__(self):
        tasks = [
            self.daily_reset,
            self.exped_reminder,
        ]
        for task in tasks:
            thread = threading.Thread(target=task, args=())
            thread.daemon = True
            thread.start()

    def exped_reminder(self):
        while True:
            now = get_singapore_time_now()
            two_mins = now + dt.timedelta(minutes=2)
            for guild in guilds.values():
                if getattr(guild, "stopped", False):
                    continue
                for e in guild.expeditions.values():
                    if equal_hour_minute(e.get_time(), two_mins):
                        # ready_markup = types.InlineKeyboardMarkup()
                        # ready_markup.add(
                        #     types.InlineKeyboardButton(
                        #         "Im ready!",
                        #         callback_data="/exped ready"
                        #     )
                        # )
                        bot.send_message(guild.chat_id,
                                         "Expedition Reminder:\n{}".format(render_expedition(e)),
                                         parse_mode="Markdown",
                                         # reply_markup=ready_markup,
                                         )
            time.sleep(60)

    def daily_reset(self):
        while True:
            now = get_singapore_time_now()
            for guild in guilds.values():
                if getattr(guild, "stopped", False):
                    continue
                if now.hour == guild.daily_reset_time:
                    guild.reset_expeditions()
                    guild.update_fort_history()
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
