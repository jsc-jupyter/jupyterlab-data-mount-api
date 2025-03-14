import json
import logging
import os
import socket
import sys
from copy import deepcopy

from jsonformatter import JsonFormatter
from values import base_mount_dir

logged_logger_name = "DataMount"
logger = None


class ExtraFormatter(logging.Formatter):
    dummy = logging.LogRecord(None, None, None, None, None, None, None)
    ignored_extras = [
        "args",
        "asctime",
        "created",
        "exc_info",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
    ]

    def format(self, record):
        extra_txt = ""
        for k, v in record.__dict__.items():
            if k not in self.dummy.__dict__ and k not in self.ignored_extras:
                extra_txt += " --- {}={}".format(k, v)
        message = super().format(record)
        return message + extra_txt


# Translate level to int
def get_level(level_str):
    if type(level_str) == int:
        return level_str
    elif level_str.upper() in logging._nameToLevel.keys():
        return logging._nameToLevel[level_str.upper()]
    elif level_str.upper().startswith("DEACTIVATE"):
        return 99
    else:
        try:
            return int(level_str)
        except ValueError:
            pass
    raise NotImplementedError(f"{level_str} as level not supported.")


# supported classes
supported_handler_classes = {
    "stream": logging.StreamHandler,
    "file": logging.handlers.TimedRotatingFileHandler,
    "smtp": logging.handlers.SMTPHandler,
    "syslog": logging.handlers.SysLogHandler,
}

# supported formatters and their arguments
hostname = os.environ.get("HOSTNAME", "unknown")
supported_formatter_classes = {
    "json": JsonFormatter,
    "simple": ExtraFormatter,
    "simple_user": ExtraFormatter,
}
json_fmt = {
    "asctime": "asctime",
    "levelno": "levelno",
    "levelname": "levelname",
    "logger": logged_logger_name,
    "hostname": hostname,
    "file": "pathname",
    "line": "lineno",
    "function": "funcName",
    "Message": "message",
}
simple_fmt = f"%(asctime)s logger={logged_logger_name} hostname={hostname} levelno=%(levelno)s levelname=%(levelname)s file=%(pathname)s line=%(lineno)d function=%(funcName)s : %(message)s"
simple_user = f"%(asctime)s levelname=%(levelname)s file=%(pathname)s line=%(lineno)d: %(message)s"
supported_formatter_kwargs = {
    "json": {"fmt": json_fmt, "mix_extra": True},
    "simple": {"fmt": simple_fmt},
    "simple_user": {"fmt": simple_user},
}


def getLogger():
    global logger
    if not logger:
        logger = createLogger()
    return logger


def createLogger():
    logging_config_path = os.environ.get(
        "LOGGING_CONFIG_FILE", "/mnt/config/logging.json"
    )
    logger = logging.getLogger()
    logging_config = {
        "stream": {
            "enabled": True,
            "level": 10,
            "formatter": "simple",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "enabled": True,
            "level": 20,
            "formatter": "simple_user",
            "filename": os.path.join(base_mount_dir, "mount.log"),
        },
    }
    logger.setLevel(10)
    if logging_config_path and os.path.exists(logging_config_path):
        with open(logging_config_path, "r") as f:
            logging_config_update = json.load(f)
        logging_config.update(logging_config_update)

    logger_handlers = logger.handlers
    handler_names = [x.name for x in logger.handlers]
    for handler_name, handler_config in logging_config.items():
        if (not handler_config.get("enabled", False)) and handler_name in handler_names:
            # Handler was disabled, remove it
            logger.debug(f"Logging handler remove ({handler_name}) ... ")
            logger.handlers = [x for x in logger_handlers if x.name != handler_name]
            logger.debug(f"Logging handler remove ({handler_name}) ... done")
        elif handler_config.get("enabled", False):
            # Recreate handlers which has changed their config
            configuration = deepcopy(handler_config)

            # map some special values
            if handler_name == "stream":
                if configuration["stream"] == "ext://sys.stdout":
                    configuration["stream"] = sys.stdout
                elif configuration["stream"] == "ext://sys.stderr":
                    configuration["stream"] = sys.stderr
            elif handler_name == "syslog":
                if configuration["socktype"] == "ext://socket.SOCK_STREAM":
                    configuration["socktype"] = socket.SOCK_STREAM
                elif configuration["socktype"] == "ext://socket.SOCK_DGRAM":
                    configuration["socktype"] = socket.SOCK_DGRAM

            _ = configuration.pop("enabled")
            formatter_name = configuration.pop("formatter")
            level = get_level(configuration.pop("level"))
            none_keys = []
            for key, value in configuration.items():
                if value is None:
                    none_keys.append(key)
            for x in none_keys:
                _ = configuration.pop(x)

            # Create handler, formatter, and add it
            handler = supported_handler_classes[handler_name](**configuration)
            formatter = supported_formatter_classes[formatter_name](
                **supported_formatter_kwargs[formatter_name]
            )
            handler.name = handler_name
            handler.setLevel(level)
            handler.setFormatter(formatter)
            if handler_name in handler_names:
                # Remove previously added handler
                logger.handlers = [x for x in logger_handlers if x.name != handler_name]
            logger.addHandler(handler)

            if "filename" in configuration:
                # filename is already used in log.x(extra)
                configuration["file_name"] = configuration["filename"]
                del configuration["filename"]
            logger.debug(
                f"Logging handler added ({handler_name})",
                extra=configuration,
            )
    return logger
