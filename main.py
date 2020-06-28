import telebot
import threading
import time
import os
import logging
import json
from flask import Flask, request

import models as m
from renderers import *
from custom_errors import *
import utils

from dotenv import load_dotenv
load_dotenv()

__token__ = os.getenv("TG_TOKEN")
telebot.logger.setLevel(logging.INFO)
bot = telebot.AsyncTeleBot(__token__)

guilds = m.Guilds.load()

with open('feature_whitelist.json') as f:
    __feature_whitelist__ = json.load(f)

with open('sauron.json') as f:
    __sauron__ = json.load(f)
print(__sauron__)


################################
#       Middleware             #
################################
def needs_to_be_sauroned(message):
    try:
        return message.chat.id in __sauron__["target"] and message.text is not None and message.text[0] is not "/"
    except Exception as e:
        logging.exception(e)
        return False


@bot.message_handler(func=needs_to_be_sauroned)
def handle_sauron(message):
    nazgul = "[({}){}]:{}".format(message.chat.title, message.from_user.username, message.text)
    print(nazgul)
    bot.send_message(__sauron__["out"], nazgul)


# TODO: This is hack to keep fort feature only for ascent
def ensure_feature_whitelisted(command, message):
    command = command.replace("/", "", 1)
    whitelist = __feature_whitelist__.get(command, None)
    if whitelist is not None and message.chat.id not in whitelist:
        raise FeatureForbidden(message.chat.id)


def _update_pinned_msg(guild):
    if guild.pinned_message_id is not None:
        bot.edit_message_text(render_guild_admin(guild),
                              chat_id=guild.chat_id,
                              message_id=guild.pinned_message_id,
                              parse_mode="Markdown",
                              reply_markup=render_poll_markup(guild))


def process_command(commands, message, doc):
    try:
        parts = message.text.split(' ')
        ensure_feature_whitelisted(parts[0], message)
        guild = guilds.get(message.chat.id)
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
                                 disable_notification=True,
                                 reply_markup=answer.reply_markup,
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
        'reassign': fort_reassign,
    }
    handle_callback(cb_handlers, call)


################################
#       Expedition Handlers    #
################################
def exped_new(message):
    doc = """Example:
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
        return m.MessageReply("Expedition created: {} {}".format(escape_for_markdown(e.title), time))
    except ValueError:
        raise WrongCommandError(doc)


def exped_title(message):
    doc = """Example:
/exped title oldtitle newtitle
        """
    parts = message.text.split(' ')
    if len(parts) != 4:
        raise WrongCommandError(doc)

    guild = guilds.get(message.chat.id)
    guild.set_expedition_title(parts[2], parts[3])
    return m.MessageReply("{} updated to {}".format(escape_for_markdown(parts[2]), escape_for_markdown(parts[3])))


def exped_description(message):
    doc = """Example:
/exped desc name description
    """
    parts = message.text.split(' ', 3)
    if len(parts) < 3:
        raise WrongCommandError(doc)
    if len(parts) == 3:
        parts = parts + [""]

    guild = guilds.get(message.chat.id)
    e = guild.set_expedition_description(parts[2], parts[3])
    return m.MessageReply("{} description updated".format(escape_for_markdown(e.title)))


def exped_time(message):
    doc = """Example:
/exped time team HHMM
        """
    parts = message.text.split(' ')
    if len(parts) != 4:
        raise WrongCommandError(doc)
    try:
        guild = guilds.get(message.chat.id)
        e = guild.set_expedition_time(parts[2], parts[3])
        return m.MessageReply("{} updated to {}".format(escape_for_markdown(e.title), parts[3]))
    except ValueError:
        raise WrongCommandError(doc)


def exped_delete(message):
    doc = """Example:
/exped delete team
    """
    parts = message.text.split(' ')
    if len(parts) == 3:
        guild = guilds.get(message.chat.id)
        guild.delete_expedition(parts[2])
        return m.MessageReply("{} deleted.".format(parts[2]))
    else:
        raise WrongCommandError(doc)


def exped_reg(message):
    doc = """Example:
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


def exped_daily(message):
    doc = """Example:
/exped daily team
/exped daily team [label]
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

    e, success = guild.daily_expedition(title, handle_id, handle, label)
    word = "in to" if success else "out of"
    return m.MessageReply("{} checked {} daily {}".format(handle, word, e.title))
    

def exped_view(message):
    doc = """Example:
/exped view
/exped view [team]
    """
    parts = message.text.split(' ')
    if len(parts) == 3:
        team = parts[2]
    else:
        team = None
    guild = guilds.get(message.chat.id)
    if team:
        exped = guild.get_expedition(team)
        return m.MessageReply(render_expedition_detail(exped), temporary=False)
    else:
        expeds = list(guild.expeditions.values())
        return m.MessageReply(render_expeditions(expeds,
                                             guild_reset_time=guild.daily_reset_time,
                                             filter=False
                                             ),
                          temporary=False)


def exped_ready(message):
    doc = """Example:
/exped ready team
/exped ready team [label]
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

    e, result = guild.ready_expedition(title, handle_id, handle, label)
    bot.edit_message_text(render_expedition_reminder(e),
                          chat_id=guild.chat_id,
                          message_id=message.message_id,
                          parse_mode="Markdown",
                          reply_markup=render_ready_markup(e))

    ready_string = "ready" if result else "not ready"
    return m.MessageReply("You are marked as {} for {}.".format(ready_string, e.title))


@bot.edited_message_handler(commands=['exped'])
@bot.message_handler(commands=['exped'])
def exped(message):
    exped_commands = {
        'reg': exped_reg,
        'new': exped_new,
        'delete': exped_delete,
        'time': exped_time,
        'title': exped_title,
        'desc': exped_description,
        'view': exped_view,
        'daily': exped_daily
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
    doc = """Example:
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
    doc = """Example:
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
    doc = """Example:
/fort reset_history
    """
    guild = guilds.get(message.chat.id)
    guild.reset_fort_history()
    guilds.save()
    return m.MessageReply("Fort history reset.", temporary=False)


def fort_get_history(message):
    doc = """Example:
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


def fort_get_roster(message):
    doc = """Example:
/fort get_roster
    """
    guild = guilds.get(message.chat.id)
    roster = guild.fort.get_roster()
    msg = render_fort_roster(roster)

    # Todo: escape markdown characters in message
    return m.MessageReply(msg,
                          temporary=False,
                          # reply_markup=render_fort_roster_markup()
                          )


def fort_reassign(message):
    doc = """Example:
/fort reassign
/fort reassign <out>
/fort reassign <out> <in>

    """
    player_in = None
    player_out = None
    parts = message.text.split(' ')
    if len(parts) == 2:
        player_out = message.from_user.username or message.from_user.first_name
    if len(parts) >= 3:
        player_out = parts[2]
    if len(parts) == 4:
        player_in = parts[3]
    if len(parts) > 5:
        raise WrongCommandError(doc)
    return m.MessageReply("{} {}".format(player_in, player_out), temporary=False)


@bot.edited_message_handler(commands=['fort'])
@bot.message_handler(commands=['fort'])
def fort(message):
    fort_commands = {
        'mark': fort_mark,
        'check': fort_check,
        'reset_history': fort_reset_history,
        'get_history': fort_get_history,
        'get_roster': fort_get_roster,
        # 'reassign': fort_reassign,
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
            logging.error(sent[1].result.text)
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


class GuildAutomation(object):
    def __init__(self):
        tasks = [
            self.daily_reset,
            self.exped_reminder,
            self.fort_reminder,
        ]
        for task in tasks:
            thread = threading.Thread(target=task, args=())
            thread.daemon = True
            thread.start()

    def exped_reminder(self):
        while True:
            now = utils.get_singapore_time_now()
            two_mins = now + dt.timedelta(minutes=2)
            for guild in guilds.values():
                if getattr(guild, "stopped", False):
                    continue
                for e in guild.expeditions.values():
                    if utils.equal_hour_minute(e.get_time(), two_mins): 
                        ready_markup = types.InlineKeyboardMarkup()
                        ready_markup.add(
                            types.InlineKeyboardButton(
                                "Im ready!",
                                callback_data="/exped ready {}".format(e.title)
                            )
                        )
                        bot.send_message(guild.chat_id,
                                         render_expedition_reminder(e),
                                         parse_mode="Markdown",
                                         reply_markup=ready_markup,
                                         )
            time.sleep(60)

    def daily_reset(self):
        while True:
            now = utils.get_singapore_time_now()
            for guild in guilds.values():
                if getattr(guild, "stopped", False):
                    continue
                if now.hour == guild.daily_reset_time:
                    guild.reset_expeditions()
                    guild.update_fort_history()
                    _guild_pin(guild.chat_id)
            guilds.save()
            time.sleep(60 * 60)

    def fort_reminder(self):
        while True:
            ascent_chat_id = -1001235725395
            guild = guilds.get(ascent_chat_id)
            roster = guild.fort.get_roster()
            now = utils.get_singapore_time_now()
            if now.hour == 20 and now.minute == 55:
                bot.send_message(ascent_chat_id,  # hard coded ascent chat id
                                 "Fort Reminder:\n\n" + render_fort_roster(roster),
                                 parse_mode="Markdown",
                                 )
            time.sleep(60)


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
