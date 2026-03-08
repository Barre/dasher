from hasher.core import Hasher, fqn
from hasher.rules.other import RULES, _make_optional_rules


def _build_default_hasher() -> Hasher:
    rules = list(RULES) + _make_optional_rules()
    return Hasher(rules=tuple(rules))


DEFAULT_HASHER: Hasher = _build_default_hasher()

__all__ = ["Hasher", "DEFAULT_HASHER", "fqn"]
