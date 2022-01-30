from enum import Enum
from sqlite3 import PrepareProtocol


class ItemType(Enum):
    WEAPON = 1
    CHARACTER = 2

    def __conform__(self, protocol):
        if protocol is PrepareProtocol:
            return self.value
        raise TypeError
