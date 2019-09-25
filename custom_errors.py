class GuildError(Exception):
    pass


class ExpeditionExistsError(GuildError):
    pass


class ExpeditionFullError(GuildError):
    pass


class ExpeditionNotFoundError(GuildError):
    pass
