from datetime import datetime
from custom_errors import *
import pickle


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
    def __init__(self, id, handle, label=None):
        self.tg_handle = handle
        self.tg_id = id
        self.label = label

    def __eq__(self, other):
        if type(other) is not ExpeditionMember:
            return False
        return self.tg_id == other.tg_id and self.tg_handle == other.tg_handle and self.label == other.label


class Expedition:
    def __init__(self, title, time):
        self.time = datetime.strptime(time, "%H%M").time()
        self.title = title
        self.members = []

    def set_time(self, time_string):
        self.time = datetime.strptime(time_string, "%H%M").time()


class Fort:
    def __init__(self):
        self.reminder_time = None
        self.roster = []


class Guild:
    def __init__(self):
        self.members = []
        self.expeditions = {}
        self.fort = Fort()
        self.pinned_message_id = None

    # Members
    # TODO

    # Expeditions
    def new_expedition(self, title, time):
        if title not in self.expeditions:
            self.expeditions[title] = Expedition(title, time)
            return self.expeditions[title]
        else:
            raise ExpeditionExistsError

    def set_expedition_time(self, title, time):
        e = self.expeditions[title]
        e.set_time(time)
        self.expeditions[title] = e
        return self.expeditions[title]

    def get_expedition(self, title):
        return self.expeditions.get(title, None)

    def delete_expedition(self, title):
        return self.expeditions.pop(title, None)

    def checkin_expedition(self, title, tg_id, handle, label=None):
        try:
            e = self.expeditions[title]
        except KeyError:
            raise ExpeditionNotFoundError
        if len(e.members) >= 10:
            raise ExpeditionFullError
        p = ExpeditionMember(tg_id, handle, label)
        if p not in e.members:
            e.members.append(p)
            return self.expeditions[title], p

    def checkout_expedition(self, title, tg_id, handle, label=None):
        try:
            e = self.expeditions[title]
        except KeyError:
            raise ExpeditionNotFoundError
        p = ExpeditionMember(tg_id, handle, label)
        if p in e.members:
            e.members.remove(p)
            return self.expeditions[title], p

    def save(self):
        with open("guild.pickle", "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load():
        with open("guild.pickle", "rb") as f:
            return pickle.load(f)


    # Fort
    # TODO
