class GuildError(Exception):
    def __init__(self):
        self.message = "A guild error."


class ExpeditionExistsError(GuildError):
    def __init__(self):
        self.message = "Expedition already exists."


class ExpeditionFullError(GuildError):
    def __init__(self):
        self.message = "Expedition is full."


class ExpeditionNotFoundError(GuildError):
    def __init__(self):
        self.message = "Expedition not found"


class ExpedMemberAlreadyExists(GuildError):
    def __init__(self):
        self.message = "Member already in expedition."


class ExpedMemberNotFound(GuildError):
    def __init__(self):
        self.message = "Member not found in expedition."


class WrongCommandError(GuildError):
    def __init__(self, doc=""):
        self.message = "Improper command."
        if len(doc) > 0:
            self.message += "\n{}".format(doc)
