""" Logging for PyLabTools.

All package modules log to children of the ``"pylabtools"`` logger. As a library, PyLabTools only
installs a :class:`logging.NullHandler`; call :func:`enable` to send log messages somewhere.
"""
import logging

LOGGER_NAME = "pylabtools"
DEFAULT_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"

logger = logging.getLogger(LOGGER_NAME)
logger.addHandler(logging.NullHandler())


def get_logger(name=None):
    """ Return the package logger, or a child of it.

    :param name: Optional child name, e.g. ``__name__`` of a module inside the package.
    """
    if name is None or name == LOGGER_NAME:
        return logger
    if name.startswith(LOGGER_NAME + "."):
        name = name[len(LOGGER_NAME) + 1:]
    return logger.getChild(name)


def enable(level=logging.INFO, file=None, stream=True, fmt=DEFAULT_FORMAT):
    """ Attach handlers to the package logger.

    :param level: Logging level for the package logger and the new handlers.
    :param file: Optional path of a log file to append to.
    :param stream: If True, also log to stderr.
    :param fmt: Format string for the new handlers.
    :return: List of the handlers that were added, so they can be passed to :func:`disable`.
    """
    formatter = logging.Formatter(fmt)
    handlers = []
    if stream:
        handlers.append(logging.StreamHandler())
    if file is not None:
        handlers.append(logging.FileHandler(file))
    for handler in handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return handlers


def disable(handlers):
    """ Remove and close handlers previously returned by :func:`enable`.

    :param handlers: Handlers to remove from the package logger.
    """
    for handler in handlers:
        logger.removeHandler(handler)
        handler.close()
