class GuildError(Exception):
    def __init__(self):
        self.message = "A guild error."


class GuildNotFoundError(GuildError):
    def __init__(self):
        self.message = "Guild is not initialized. Run /start first."


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


class ExpedMemberNotFoundError(GuildError):
    def __init__(self):
        self.message = "Member not found in expedition."


class FortAttendanceExistsError(GuildError):
    def __init__(self):
        self.message = "Attendance already marked."


class FortAttendanceNotFoundError(GuildError):
    def __init__(self):
        self.message = "Attendance not found."


class WrongCommandError(GuildError):
    def __init__(self, doc=""):
        self.message = "Invalid command."
        if len(doc) > 0:
            self.message += "\n{}".format(doc)


class FeatureForbidden(GuildError):
    def __init__(self, id):
        self.message = "Feature forbidden in chat {}".format(id)
