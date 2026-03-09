from hasher.core import Hasher, fqn
from hasher.rules.backends import RULES as BACKEND_RULES
from hasher.rules.expr import RULES as EXPR_RULES
from hasher.rules.other import RULES as OTHER_RULES


DEFAULT_HASHER: Hasher = Hasher(rules=tuple(OTHER_RULES + BACKEND_RULES + EXPR_RULES))

__all__ = ["Hasher", "DEFAULT_HASHER", "fqn"]
