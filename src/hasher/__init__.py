from hasher.core import Hasher
from hasher.rules.other import EAGER_RULES, _make_lazy_rules


def _build_default_hasher() -> Hasher:
    rules = list(EAGER_RULES) + _make_lazy_rules()
    return Hasher(rules=tuple(rules))


DEFAULT_HASHER: Hasher = _build_default_hasher()

__all__ = ["Hasher", "DEFAULT_HASHER"]
