class ArenaError(Exception):
    # Base class for rule violations handled by the UI layer
    pass


class AlreadyAttemptedError(ArenaError):
    pass


class OwnQuizError(ArenaError):
    pass


class QuizAlreadyExistsError(ArenaError):
    pass


class AccountLockedError(ArenaError):
    pass


class InvalidPinError(ArenaError):
    pass


class HiddenQuizError(ArenaError):
    pass