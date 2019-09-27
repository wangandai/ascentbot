from datetime import datetime
from custom_errors import *
import pickle
from threading import Lock
import storage
import os

storage = storage.Storage()


class PlayerStats:
    def __init__(self):
        pass

    def __eq__(self, other):  # TODO
        return True


class TelegramInfo:
    def __init__(self):
        self.handle = None
        self.id = None

    def __eq__(self, other):
        if type(other) is not TelegramInfo:
            return False
        return self.id == other.id


class Player:
    def __init__(self):
        self.telegram = TelegramInfo()
        self.stats = PlayerStats()

    def __eq__(self, other):
        if type(other) is not Player:
            return False
        return self.telegram == other.telegram and self.stats == other.stats


class ExpeditionMember:
    def __init__(self, tg_id, handle, label=""):
        self.tg_handle = handle
        self.tg_id = tg_id
        self.label = label

    def __eq__(self, other):
        if type(other) is not ExpeditionMember:
            return False
        return self.tg_id == other.tg_id and self.label.lower() == other.label.lower()


class Expedition:
    def __init__(self, title, time, description=""):
        self.time = datetime.strptime(time, "%H%M").time()
        self.title = title
        self.members = []
        self.description = description

    def set_time(self, time_string):
        self.time = datetime.strptime(time_string, "%H%M").time()

    def set_description(self, description):
        self.description = description


class Fort:
    def __init__(self):
        self.reminder_time = None
        self.roster = []


class Guild:
    def __init__(self):
        self.title = ""
        self.members = []
        self.expeditions = {}
        self.fort = Fort()
        self.pinned_message_id = None
        self.chat_id = None
        self.lock = Lock()
        self.daily_reset_time = 3

    # Members
    # TODO

    # Expeditions
    def new_expedition(self, title, time, description=""):
        with self.lock:
            try:
                self.get_expedition(title)
            except ExpeditionNotFoundError:
                slug = title.lower()
                self.expeditions[slug] = Expedition(title, time, description)
                return self.expeditions[slug]
            else:
                raise ExpeditionExistsError

    def set_expedition_time(self, title, time):
        with self.lock:
            e = self.get_expedition(title)
            e.set_time(time)
            return e

    def get_expedition(self, title):
        try:
            slug = title.lower()
            return self.expeditions[slug]
        except KeyError:
            raise ExpeditionNotFoundError

    def delete_expedition(self, title):
        with self.lock:
            try:
                slug = title.lower()
                del self.expeditions[slug]
            except KeyError:
                raise ExpeditionNotFoundError

    def checkin_expedition(self, title, tg_id, handle, label=""):
        with self.lock:
            e = self.get_expedition(title)
            p = ExpeditionMember(tg_id, handle, label)
            if p not in e.members:
                if len(e.members) >= 10:
                    raise ExpeditionFullError
                e.members.append(p)
                return e, p
            else:
                raise ExpedMemberAlreadyExists

    def checkout_expedition(self, title, tg_id, handle, label=""):
        with self.lock:
            e = self.get_expedition(title)
            p = ExpeditionMember(tg_id, handle, label)
            if p in e.members:
                e.members.remove(p)
                return e, p
            else:
                raise ExpedMemberNotFound

    def set_reset_time(self, time):
        with self.lock:
            self.daily_reset_time = time

    def reset_expeditions(self):
        with self.lock:
            for e in self.expeditions:
                self.expeditions[e].members = []

    def save(self):
        with self.lock:
            with open("guilds/{}.pickle".format(self.chat_id), "wb") as f:
                pickle.dump(self, f)

    @staticmethod
    def load(filename):
        with open(filename, "rb") as f:
            return pickle.load(f)

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['lock']
        return state

    def __setstate__(self, d):
        self.__dict__.update(d)
        self.lock = Lock()

    # Fort
    # TODO


class Guilds:
    savefile = "{}.guilds".format(os.getenv("MODE", "dev"))

    def __init__(self):
        self.guilds = {}

    def get(self, guild_chat_id):
        try:
            return self.guilds[guild_chat_id]
        except KeyError:
            raise GuildNotFoundError

    def set(self, guild_chat_id, guild):
        self.guilds[guild_chat_id] = guild

    def values(self):
        return self.guilds.values()

    def keys(self):
        return self.guilds.keys()

    def save(self):
        storage.savefile(self, self.savefile)

    @staticmethod
    def load():
        _g = Guilds()
        g = storage.loadfile(Guilds.savefile)
        if g is not None:
            _g.__dict__.update(g.__dict__)
        return _g
