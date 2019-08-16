import telebot
from telebot import types
from pprint import pprint


def get_tg_token():
    with open('tg_token', 'r') as f:
        return f.readline()


def get_polls():
    with open('polls', 'r') as f:
        return f.readlines()


__token__ = get_tg_token()
__polls__ = get_polls()
count = 0

bot = telebot.TeleBot(__token__)


def create_poll_markup():
    markup = types.InlineKeyboardMarkup()
    for poll in __polls__:
        markup.add(types.InlineKeyboardButton(poll, callback_data=poll))
    return markup


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    print(message)
    bot.send_message(message.chat.id, 'Boss today:', reply_markup=create_poll_markup())


@bot.callback_query_handler(func=lambda call: call.data in __polls__)
def receive_poll(call):
    print(call)
    global count
    count = count + 1
    bot.edit_message_text("thanks {}".format(count),
                          message_id=call.message.message_id,
                          chat_id=call.message.chat.id,
                          reply_markup=create_poll_markup())


bot.polling(none_stop=True)