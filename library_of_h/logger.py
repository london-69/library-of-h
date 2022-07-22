from __future__ import annotations

import logging
import logging.handlers
import os
from enum import IntEnum, auto

from library_of_h.constants import APP_LOGS_LOCATION
from library_of_h.signals_hub.signals_hub import logger_signals


class MainType(IntEnum):
    EXPLORER = auto()
    DOWNLOADER = auto()


class SubType(IntEnum):
    DBMGR = auto()
    NAMGR = auto()
    EXTTR = auto()
    DLDR = auto()
    BASE = auto()


class ServiceType(IntEnum):
    HITOMI = auto()
    NHENTAI = auto()


class FileHandler(logging.handlers.RotatingFileHandler):

    _logger_widget: "Logs"

    @classmethod
    def set_logger_widget(cls, logger_widget: "Logs") -> None:
        cls._logger_widget = logger_widget

    def __init__(self) -> None:
        super().__init__(
            APP_LOGS_LOCATION,
            mode="a",
            maxBytes=102_400,  # 100 KiB
            backupCount=2,
            encoding="utf-8",
            delay=True,
            errors=None,
        )

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        if record.levelno != logging.DEBUG:
            self._logger_widget.appendPlainText(self.format(record))
        if record.levelno >= logging.WARNING:
            logger_signals.create_logs_icon_signal.emit()
        if record.levelno >= logging.ERROR:
            logger_signals.halt_signal.emit()
            logger_signals.create_message_box_signal.emit(record.levelname)


def get_logger(
    main_type: MainType, service_type: ServiceType, sub_type: SubType
) -> logging.Logger:
    name = f"{main_type.name}:{service_type.name}:{sub_type.name}"
    logger = logging.getLogger(name=name)
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG)

    file_handler = FileHandler()
    formatter = logging.Formatter(
        fmt="<{levelname}><{name}><{asctime}>{msg}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger


def set_logger_widget(logger_widget: "Logs") -> None:
    """
    Sets the logger global widget for the Handler.
    """
    FileHandler.set_logger_widget(logger_widget)
