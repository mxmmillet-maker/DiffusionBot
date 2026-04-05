from importlib import import_module

from adapters.base import AbstractPlatformAdapter

_REGISTRY: dict[str, type[AbstractPlatformAdapter]] = {}


def register(cls: type[AbstractPlatformAdapter]):
    """Decorateur pour enregistrer un adaptateur."""
    _REGISTRY[cls.slug] = cls
    return cls


def get_adapter(slug: str) -> type[AbstractPlatformAdapter]:
    """Recupere la classe d'adaptateur par son slug."""
    if slug not in _REGISTRY:
        raise KeyError(f"Adaptateur inconnu: {slug}")
    return _REGISTRY[slug]


def list_adapters() -> dict[str, type[AbstractPlatformAdapter]]:
    return dict(_REGISTRY)


def load_all_adapters():
    """Import tous les modules du dossier platforms/ pour declencher @register."""
    import pkgutil

    import adapters.platforms as pkg

    for _importer, modname, _ispkg in pkgutil.iter_modules(pkg.__path__):
        import_module(f"adapters.platforms.{modname}")
