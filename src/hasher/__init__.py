from hasher.core import Hasher, fqn
from hasher.rules.other import RULES


DEFAULT_HASHER: Hasher = Hasher(rules=tuple(RULES))

__all__ = ["Hasher", "DEFAULT_HASHER", "fqn"]
