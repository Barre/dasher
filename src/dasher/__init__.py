from dasher.core import Hasher, fqn
from dasher.rules.backends import RULES as BACKEND_RULES
from dasher.rules.expr import RULES as EXPR_RULES
from dasher.rules.fallback import RULES as FALLBACK_RULES
from dasher.rules.functions import RULES as FUNCTION_RULES
from dasher.rules.other import RULES as OTHER_RULES


DEFAULT_HASHER: Hasher = Hasher(
    rules=OTHER_RULES + FUNCTION_RULES + BACKEND_RULES + EXPR_RULES + FALLBACK_RULES
)

__all__ = ["Hasher", "DEFAULT_HASHER", "fqn"]
