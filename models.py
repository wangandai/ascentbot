from datetime import datetime
from custom_errors import *
from threading import Lock
import database
import os
import json
import ascentapi


class Player:
    def __init__(self, tg_id: str = "", tg_handle: str = "", label: str = ""):
        self.tg_handle = tg_handle
        self.tg_id = tg_id
        self.label = label

    def __eq__(self, other):
        if type(other) is not Player:
            return False
        return self.__str__() == other.__str__()

    def __hash__(self):
        return hash(self.__str__())

    def __str__(self):
        return json.dumps(self.__dict__, sort_keys=True)

    @classmethod
    def from_json(cls, data):
        return cls(**data)


class Expedition:
    def __init__(self, title: str = "", time: str = "1200", description: str = "", members: list = None, ready: list = None, daily: list = None):
        self.set_time(time)
        self.title = title
        self.members = members or []
        self.ready = ready or []
        self.description = description
        self.daily = daily or []

    def set_time(self, time):
        datetime.strptime(time, '%H%M')  # check that time corresponds to format
        self.time = time

    def set_description(self, description):
        self.description = description

    def get_time(self):
        return datetime.strptime(self.time, "%H%M").time()

    @classmethod
    def from_json(cls, data):
        data["members"] = [Player.from_json(m) for m in data.get("members", list())]
        data["ready"] = [Player.from_json(m) for m in data.get("ready", list())]
        data["daily"] = [Player.from_json(m) for m in data.get("daily", list())]
        return cls(**data)


class Fort:
    def __init__(self, roster: list = None, attendance: list = None, history: dict = None):
        self.roster = roster or []
        self.attendance = attendance or []
        self.history = history or {}

    @classmethod
    def from_json(cls, data):
        data["attendance"] = [Player.from_json(e) for e in data.get("attendance", list())]
        return cls(**data)

    def get_roster(self):
        return ascentapi.get_fort_roster()


class Guild:
    def __init__(self, title: str = "",
                 members: list = None,
                 expeditions: dict = None,
                 fort: Fort = None,
                 pinned_message_id: int = None,
                 chat_id: int = None,
                 daily_reset_time: int = 3,
                 stopped: bool = False):
        self.title = title
        self.members = members or []
        self.expeditions = expeditions or {}
        self.fort = fort or Fort()
        self.pinned_message_id = pinned_message_id or None
        self.chat_id = chat_id or None
        self.lock = Lock()
        self.daily_reset_time = daily_reset_time
        self.stopped = stopped

    @classmethod
    def from_json(cls, data):
        data.pop("lock", None)
        data["fort"] = Fort.from_json(data["fort"])
        data["expeditions"] = {t: Expedition.from_json(e) for (t, e) in data.get("expeditions", dict()).items()}
        # TODO: Members
        return cls(**data)

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

    def daily_expedition(self, title, tg_id, handle, label=""):
        with self.lock:
            e = self.get_expedition(title)
            p = Player(tg_id, handle, label)
            if p in e.daily:
                e.daily.remove(p)
                return e, False
            else: 
                if len(e.daily) >= 10:
                    raise ExpeditionFullError
                e.daily.append(p)
                return e, True

    def checkin_expedition(self, title, tg_id, handle, label=""):
        with self.lock:
            e = self.get_expedition(title)
            p = Player(tg_id, handle, label)
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
            p = Player(tg_id, handle, label)
            if p in e.members:
                e.members.remove(p)
                return e, p
            else:
                raise ExpedMemberNotFoundError

    def ready_expedition(self, title, tg_id, handle, label=""):
        with self.lock:
            e = self.get_expedition(title)
            p = Player(tg_id, handle, label)
            if p in e.ready:
                e.ready.remove(p)
                return e, False
            else:
                e.ready.append(p)
                return e, True

    def set_reset_time(self, time):
        with self.lock:
            self.daily_reset_time = time

    def reset_expeditions(self):
        with self.lock:
            for e in self.expeditions:
                self.expeditions[e].members = list(self.expeditions[e].daily)
                self.expeditions[e].ready = []

    def fort_mark(self, tg_id, handle, label=""):
        with self.lock:
            p = Player(tg_id, handle, label)
            if p in self.fort.attendance:
                raise FortAttendanceExistsError
            self.fort.attendance.append(p)

    def fort_unmark(self, tg_id, handle, label=""):
        with self.lock:
            p = Player(tg_id, handle, label)
            if p not in self.fort.attendance:
                raise FortAttendanceNotFoundError
            self.fort.attendance.remove(p)

    def get_attendance_today(self, tg_id, handle, label=""):
        p = Player(tg_id, handle, label)
        if p in self.fort.attendance:
            return True
        return False

    def update_fort_history(self):
        with self.lock:
            for p in self.fort.attendance:
                p_str = str(p)
                count = self.fort.history.get(p_str, 0)
                self.fort.history[p_str] = count + 1
            self.fort.attendance = []

    def get_history_of(self, tg_id, handle, label=""):
        p = Player(tg_id, handle, label)
        p_str = str(p)
        try:
            return self.fort.history[p_str]
        except KeyError:
            raise FortAttendanceNotFoundError

    def reset_fort_history(self):
        self.fort = Fort()

    def get_history_all(self):
        combined = {}
        for p in self.fort.attendance:
            combined[str(p)] = 1
        for p_Str in self.fort.history:
            combined[p_Str] = self.fort.history.get(p_Str, 0) + combined.get(p_Str, 0)
        return combined

    def __eq__(self, other):
        if type(other) is not Guild:
            return False
        return self.__dict__ == other.__dict__


class Guilds:
    savefile = "guilds.{}.json".format(os.getenv("MODE", "dev"))

    def __init__(self, guilds: dict = None, storage: database.Storage = None):
        self.guilds = guilds or {}
        self.storage = storage or database.Storage()

    def get(self, guild_chat_id, ignore_stopped=False):
        try:
            g = self.guilds[guild_chat_id]
            if g.stopped and not ignore_stopped:
                raise GuildNotFoundError
            else:
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
        saveobj = self.__dict__.copy()
        del saveobj["storage"]
        self.storage.savefile(saveobj, self.savefile, "json")

    @staticmethod
    def load(storage: database.Storage = None):
        if storage is None:
            storage = database.Storage()

        t = storage.loadfile(Guilds.savefile, "json")
        if t is None:
            return Guilds()
        return Guilds.from_json(t)


    @classmethod
    def from_json(cls, data):
        data.pop("storage", None)
        data["guilds"] = {int(k): Guild.from_json(v) for k, v in data["guilds"].items()}
        return cls(**data)


class MessageReply:
    def __init__(self, message, temporary=True, reply_markup=None):
        self.message = message
        self.temporary = temporary  # Marks reply as temporary and should be deleted to reduce clutter
        self.reply_markup = reply_markup
