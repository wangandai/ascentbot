import telebot
from telebot import types
import models as m
import datetime
import threading
import time
from custom_errors import *
import os
import logging


def get_tg_token():
    with open('tg_token', 'r') as f:
        return f.readline()


def get_polls():
    with open('polls', 'r') as f:
        return f.readlines()


def load_guilds():
    gs = {}
    suffix = ".pickle"
    for filename in os.listdir("guilds"):
        if filename.endswith(suffix):
            g = m.Guild.load("guilds/{}".format(filename))
            gs[g.chat_id] = g
    return gs


__token__ = get_tg_token()
__polls__ = get_polls()
__test_chat_id__ = "-331833019"
__pin_msg_id__ = None
guilds = m.Guilds()


telebot.logger.setLevel(logging.DEBUG)
bot = telebot.AsyncTeleBot(__token__)


def render_expedition(expedition):
    msg = "\n"
    msg += "*{}* {} ({} 👥)\n".format(expedition.title,
                                      datetime.time.strftime(expedition.time, "%H%M"),
                                      len(expedition.members))
    for i, member in enumerate(expedition.members):
        msg += "{}. [{}](tg://user?id={}) {}\n".format(i + 1, member.tg_handle, member.tg_id,
                                                       member.label if member.label is not None else "")
    return msg


def render_expeditions(guild):
    msg = "Expeditions: \n"
    expeds = list(guild.expeditions.values())
    expeds.sort(key=lambda x: x.time)
    for e in expeds:
        msg += render_expedition(e)
    if len(expeds) is 0:
        msg += "None"
    return msg


def render_guild_admin(guild):
    current_day = datetime.datetime.now().date()
    guild_msg = "Guild Admin {}/{}\n".format(current_day.month, current_day.day)
    guild_msg += render_expeditions(guild)
    return guild_msg


def create_poll_markup():
    markup = types.InlineKeyboardMarkup()
    for poll in __polls__:
        markup.add(types.InlineKeyboardButton(poll, callback_data=poll))
    return markup


def handle_command(commands, message, doc):
    try:
        guild = guilds.get(message.chat.id)
        parts = message.text.split(' ')
        if len(parts) >= 2 and parts[1] in commands:
            command_str = parts[1]
            commands[command_str](message)
            if guild.pinned_message_id is not None:
                bot.edit_message_text(render_guild_admin(guild),
                                      chat_id=message.chat.id,
                                      message_id=guild.pinned_message_id,
                                      parse_mode="Markdown")
            guild.save()
        else:
            raise WrongCommandError(doc)
    except Exception as e:
        if issubclass(type(e), GuildError):
            bot.send_message(message.chat.id, e.message)
        else:
            raise e


def exped_new(message):
    doc = """
/exped new team1 1500
    """
    parts = message.text.split(' ')
    if len(parts) != 4:
        raise WrongCommandError(doc)
    time = parts[3]
    title = parts[2]

    try:
        guild = guilds.get(message.chat.id)
        e = guild.new_expedition(title, time)
        bot.send_message(message.chat.id, "Expedition created: {} {}".format(e.title, time))
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
        bot.send_message(message.chat.id, "{} updated to {}".format(e.title, parts[3]))
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
        bot.send_message(message.chat.id, "{} deleted.".format(parts[2]))
    else:
        raise WrongCommandError(doc)


def exped_checkin(message):
    doc = """
/exped checkin team
/exped checkin team [label]
    """
    parts = message.text.split(' ')
    if len(parts) == 4:
        label = parts[3].lower()
    elif len(parts) == 3:
        label = None
    else:
        raise WrongCommandError(doc)

    title = parts[2]
    handle = message.from_user.first_name
    handle_id = message.from_user.id
    guild = guilds.get(message.chat.id)
    try:
       exped, member = guild.checkin_expedition(title, handle_id, handle, label)
       bot.send_message(message.chat.id, "{} checked in to {}".format(member.tg_handle, exped.title))
    except ValueError:
        raise WrongCommandError(doc)


def exped_checkout(message):
    doc = """
/exped checkout team
/exped checkout team [label]
    """
    parts = message.text.split(' ')
    if len(parts) == 4:
        label = parts[3]
    elif len(parts) == 3:
        label = None
    else:
        raise WrongCommandError(doc)

    title = parts[2]
    handle = message.from_user.first_name
    handle_id = message.from_user.id
    guild = guilds.get(message.chat.id)
    exped, member = guild.checkout_expedition(title, handle_id, handle, label)
    bot.send_message(message.chat.id, "{} checked out of {}".format(member.tg_handle, exped.title))


def exped_view(message):
    doc = """Possible messages:
/exped view
    """
    guild = guilds.get(message.chat.id)
    bot.send_message(message.chat.id, render_expeditions(guild), parse_mode="Markdown")


exped_commands = {
    'checkin': exped_checkin,
    'checkout': exped_checkout,
    'new': exped_new,
    'delete': exped_delete,
    'time': exped_time,
    'view': exped_view
}


@bot.edited_message_handler(commands=['exped'])
@bot.message_handler(commands=['exped'])
def exped(message):
    doc = """
/exped command [arguments...]
Available commands are : {}
    """.format([a for a in exped_commands.keys()])
    handle_command(exped_commands, message, doc)
    # bot.delete_message(message.chat.id, message.message_id)


# @bot.callback_query_handler(func=lambda call: call.data in __polls__)
# def receive_poll(call):
#     print(call)
#     global count
#     count = count + 1
#     bot.edit_message_text("thanks {}".format(count),
#                           message_id=call.message.message_id,
#                           chat_id=call.message.chat.id,
#                           reply_markup=create_poll_markup())


def guild_pin(message):
    guild = guilds.get(message.chat.id)
    guild_msg = render_guild_admin(guild)
    sent = bot.send_message(guild.chat_id, guild_msg, parse_mode="Markdown").wait()
    guild.pinned_message_id = sent.message_id
    bot.pin_chat_message(guild.chat_id, guild.pinned_message_id)


guild_commands = {
    "pin": guild_pin,
}


@bot.edited_message_handler(commands=['admin'])
@bot.message_handler(commands=['admin'])
def admin(message):
    doc = """
/guild command [arguments...]
Available commands are : {}
    """.format([a for a in guild_commands.keys()])
    handle_command(guild_commands, message, doc)


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
        guild.save()
        bot.send_message(message.chat.id, "Guild bot initialized.")


@bot.message_handler(commands=['reset_guild'])
def reset(message):
    guilds.pop(message.chat.id, None)
    start(message)


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
            now = datetime.datetime.now().time()
            for guild in guilds.values():
                for e in guild.expeditions.values():
                    if e.time.hour == now.hour and e.time.minute == now.minute:
                        bot.send_message(__test_chat_id__, render_expeditions(guild), parse_mode="Markdown")
            time.sleep(30)

    def daily_reset(self):
        while True:
            now = datetime.datetime.now().time()
            for guild in guilds.values():
                if now.hour == guild.daily_reset_time:
                    guild.reset_expeditions()
            time.sleep(60 * 60)


GuildAutomation()
bot.polling(none_stop=True)
