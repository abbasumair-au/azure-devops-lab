import logging
from functools import wraps
from typing import Callable, Type, Tuple, Any

logger = logging.getLogger(__name__)


def retry(
    times: int = 3,
    delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator qui relance une fonction en cas d'échec.

    Args:
        times: Nombre de tentatives
        delay: Secondes entre chaque tentative
        exceptions: Types d'exceptions à intercepter

    Usage:
        @retry(times=3, delay=0.5, exceptions=(ConnectionError,))
        def call_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # TODO:
            # 1. Boucler `times` fois
            # 2. Appeler func(*args, **kwargs)
            # 3. Si une exception dans `exceptions` est levée :
            #    - Logger "Attempt X/Y failed: <error>"
            #    - Attendre `delay` secondes (import time)
            # 4. Après toutes les tentatives, lever la dernière exception
            raise NotImplementedError
        return wrapper
    return decorator
