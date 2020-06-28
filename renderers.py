import utils
from telebot import types
import datetime as dt


def escape_for_markdown(s):
    for symbol in ["*", "_", "[", "]", "(", ")", ]:
        s = s.replace(symbol, "\\" + symbol)
    return s


def render_adv_text():
    return """
Advanced commands:
Register alt:
/exped reg <team> <alt>
New expedition:
/exped new <team> <HHMM> <description>
Change time:
/exped time <team> <HHMM>
"""


def render_expedition_member_line(i, p):
    return "{}. [{}](tg://user?id={}) {}\n".format(i,
                                                   escape_for_markdown(p.tg_handle),
                                                   p.tg_id,
                                                   escape_for_markdown(p.label if p.label is not None else ""))


def render_expedition_reminder(expedition):
    msg = "Expedition Reminder\n"
    msg += render_expedition(expedition)
    msg += "Ready (👥 {})\n".format(len(expedition.ready))
    for i, p in enumerate(expedition.ready):
        msg += render_expedition_member_line(i + 1, p)
    return msg + "\n"


def render_expedition(expedition):
    msg = "⚔️ {}    🕑 {}    👥 {}\n".format(escape_for_markdown(expedition.title),
                                             render_human_time(expedition.get_time()),
                                             len(expedition.members),
                                             )
    if len(expedition.description) > 0:
        msg += "📋 {}\n".format(expedition.description)
    for i, member in enumerate(expedition.members):
        msg += render_expedition_member_line(i + 1, member)
    return msg + "\n"

def render_expedition_detail(expedition):
    msg = render_expedition(expedition)
    msg += "\nDaily sign ups:\n"
    for i, member in enumerate(expedition.daily):
        msg += render_expedition_member_line(i + 1, member)
    return msg

def sort_expeditions(expeds, daily_reset_time=0):
    return sorted(expeds, key=lambda x: utils.time_shifted_back_hours(x.get_time(), daily_reset_time))


def filter_expeditions(expeds, daily_reset_time=0):
    now = utils.get_singapore_time_now()
    if 0 <= now.time().hour - daily_reset_time <= 2:  # if current time is within 2 hours after daily reset time, dont filter
        return expeds
    two_h_before = (now - dt.timedelta(hours=2)).time()
    offset = daily_reset_time
    expeds = [e for e in expeds if
              utils.time_shifted_back_hours(e.get_time(), offset) > utils.time_shifted_back_hours(two_h_before, offset)]
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
    current_day = utils.get_singapore_time_now().date()
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
    # fort_mark_button = types.InlineKeyboardButton("Went fort today",
    #                                               callback_data="/fort mark")
    # fort_check_button = types.InlineKeyboardButton("My fort count",
    #                                                callback_data="/fort check")
    # markup.row(fort_mark_button, fort_check_button)
    return markup


def render_ready_markup(e):
    ready_markup = types.InlineKeyboardMarkup()
    ready_markup.add(
        types.InlineKeyboardButton(
            "Im ready!",
            callback_data="/exped ready {}".format(e.title)
        )
    )
    return ready_markup


def render_human_time(time_obj):
    if time_obj.minute > 0:
        return time_obj.strftime("%I.%M%p").lstrip("0").lower()
    else:
        return time_obj.strftime("%I%p").lstrip("0").lower()


def render_fort_roster(roster):
    def get_name(p):
        return escape_for_markdown(p["telegram"] if p["telegram"] != "" else p["name"])

    def get_role(p):
        return escape_for_markdown(p["role"] if len(p["role"]) > 0 else "minibomb")

    msg = "*Latest Fort Roster* ({})\n\n".format(utils.get_singapore_time_now().strftime("%d/%m"))
    for i in range(20):
        if i > len(roster):
            break
        p = roster[i]
        msg += "{}. {} : {}\n".format(i + 1, get_name(p), get_role(p))
    if len(roster) > 20:
        msg += "\nBackup:\n"
        for i, p in enumerate([p for p in roster[20:] if p["name"] is not ""]):
            msg += "{}. {} : {}\n".format(i + 1, get_name(p), get_role(p))
    msg += "\nIf anyone can't make it please inform now. Thanks!"
    return msg


def render_fort_roster_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "I can't today.",
            callback_data="/fort reassign"
        )
    )
    return markup
