import telebot
from telebot import types
import models as m
import datetime
import threading
import time


def get_tg_token():
    with open('tg_token', 'r') as f:
        return f.readline()


def get_polls():
    with open('polls', 'r') as f:
        return f.readlines()


__token__ = get_tg_token()
__polls__ = get_polls()
__test_chat_id__ = "-331833019"
__pin_msg_id__ = None
count = 0

bot = telebot.TeleBot(__token__)
try:
    guild = m.Guild.load()
except:
    guild = m.Guild()


def render_error_msg(doc):
    return "Please send command in format: {}".format(doc)


def render_expedition(expedition):
    msg = "\n"
    msg += "*{}* {} ({} 👥)\n".format(expedition.title,
                                      datetime.time.strftime(expedition.time, "%H%M"),
                                      len(expedition.members))
    for i, member in enumerate(expedition.members):
        msg += "{}. [{}](tg://user?id={}) {}\n".format(i + 1, member.tg_handle, member.tg_id,
                                                       member.label if member.label is not None else "")
    return msg


def render_expeditions():
    msg = ""
    expeds = list(guild.expeditions.values())
    expeds.sort(key=lambda x: x.time)
    for e in expeds:
        msg += render_expedition(e)
    if len(expeds) is 0:
        msg = None
    return msg


def create_poll_markup():
    markup = types.InlineKeyboardMarkup()
    for poll in __polls__:
        markup.add(types.InlineKeyboardButton(poll, callback_data=poll))
    return markup


def exped_new(message):
    doc = """
/exped new team1 1500
    """
    parts = message.text.split(' ')
    if len(parts) != 4:
        bot.send_message(message.chat.id, render_error_msg(doc))
        return
    time = parts[3]
    title = parts[2]
    try:
        e = guild.new_expedition(title, time)
        bot.send_message(message.chat.id, "Expedition created: {} {}".format(e.name, time)
    except (KeyError, ValueError):
        bot.send_message(message.chat.id, render_error_msg(doc))


def exped_time(message):
    doc = """
/exped time team1 1500
        """
    parts = message.text.split(' ')
    if len(parts) != 4:
        bot.send_message(message.chat.id, render_error_msg(doc))
        return
    try:
        guild.set_expedition_time(parts[2], parts[3])
    except (KeyError, ValueError):
        bot.send_message(message.chat.id, render_error_msg(doc))



def exped_delete(message):
    doc = """
/exped delete team1
    """
    parts = message.text.split(' ')
    if len(parts) == 3:
        guild.delete_expedition(parts[2])
    else:
        bot.send_message(message.chat.id, render_error_msg(doc))
        return


def exped_checkin(message):
    doc = """
/exped checkin team1
/exped checkin team1 label
    """
    parts = message.text.split(' ')
    if len(parts) == 4:
        label = parts[3].lower()
    elif len(parts) == 3:
        label = None
    else:
        bot.send_message(message.chat.id, render_error_msg(doc))
        return

    title = parts[2]
    handle = message.from_user.first_name
    handle_id = message.from_user.id
    try:
        guild.checkin_expedition(title, handle_id, handle, label)
    except (KeyError, ValueError):
        bot.send_message(message.chat.id, render_error_msg(doc))


def exped_checkout(message):
    doc = """
/exped checkout team1
/exped checkout team1 label
    """
    parts = message.text.split(' ')
    if len(parts) == 4:
        label = parts[3]
    elif len(parts) == 3:
        label = None
    else:
        bot.send_message(message.chat.id, render_error_msg(doc))
        return

    title = parts[2]
    handle = message.from_user.first_name
    handle_id = message.from_user.id
    try:
        guild.checkout_expedition(title, handle_id, handle, label)
    except ExpeditionNotFoundError:
        bot.send_message(message.chat.id, "Expedition name not found: {}".format(title))


def exped_view(message):
    doc = """Possible messages:
/exped view
    """
    bot.send_message(message.chat.id, "Expeditions:\n{}".format(render_expeditions()), parse_mode="Markdown")


exped_commands = {
    'checkin': exped_checkin,
    'checkout': exped_checkout,
    'new': exped_new,
    'delete': exped_delete,
    'time': exped_time,
    'view': exped_view
}


@bot.message_handler(commands=['exped'])
def exped(message):
    doc = """
/exped command [arguments...]
Available commands are : {}
    """.format([a for a in exped_commands.keys()])
    print(message.text)
    parts = message.text.split(' ')
    if len(parts) >= 2 and parts[1] in exped_commands:
        command_str = parts[1]
        exped_commands[command_str](message)
    else:
        bot.send_message(message.chat.id, render_error_msg(doc))
        return
    guild.save()
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


def guild_pin(_):  # TODO: Change render_expeditions to render all
    current_day = datetime.datetime.now().date()
    guild_msg = "Guild Admin {}/{}\n".format(current_day.month, current_day.day)
    guild_msg += render_expeditions() if render_expeditions() is not None else ""
    if guild.pinned_message_id is None:
        guild.pinned_message_id = bot.send_message(__test_chat_id__, guild_msg, parse_mode="Markdown").message_id
    else:
        bot.unpin_chat_message(__test_chat_id__, guild.pinned_message_id)
        guild.pinned_message_id = bot.send_message(__test_chat_id__, guild_msg, parse_mode="Markdown").message_id
    bot.pin_chat_message(__test_chat_id__, guild.pinned_message_id)


guild_commands = {
    "pin": guild_pin,
}


@bot.message_handler(commands=['admin'])
def admin(message):
    doc = """
/guild command [arguments...]
Available commands are : {}
    """.format([a for a in guild_commands.keys()])
    print(message.text)
    parts = message.text.split(' ')
    if len(parts) >= 2 and parts[1] in guild_commands:
        command_str = parts[1]
        guild_commands[command_str](message)
    else:
        bot.send_message(message.chat.id, render_error_msg(doc))
        return
    guild.save()


class GuildAutomation(object):
    def __init__(self):

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True
        thread.start()

    def run(self):
        while True:
            now = datetime.datetime.now().time()

            # Daily pinned message

            # Expedition Reminders
            for e in guild.expeditions.values():
                if e.time.hour == now.hour and e.time.minute == now.minute:
                    bot.send_message(__test_chat_id__, render_expeditions(), parse_mode="Markdown")
            time.sleep(30)


GuildAutomation()
bot.polling(none_stop=True)
