import logging
import threading

# - log configurations - #
LOGGER_NAME = "slt_log"
LOGGER_LEVEL = logging.DEBUG
LOGGER_FORMAT = "[%(asctime)s] [%(levelname)s::%(name)s] [%(message)s]"
LOGGER_FILE_NAME = "slt.log"
LOGGER_GUI_SIGNAL = None

# - generic log messages - #
INIT_MSG = "Initializing %s"
CMPLT_MSG = "%s complete"
SET_MSG = "Setting %s on %s with %s"


class GuiStreamHandler(logging.StreamHandler):
    """ Simple sub-class of the stream handler to write data to a gui log window in addition to the stream.
    """

    def __init__(self, ui_log_sig):
        super().__init__()
        self.ui_log_sig = ui_log_sig

    def emit(self, record):
        msg = self.format(record)
        self.ui_log_sig.emit(msg)
        super().emit(record)


def configure_slt_log():
    """ Configure the spherexlabtools logger classes.
    """
    slt_logger = logging.getLogger(LOGGER_NAME)
    slt_logger.setLevel(LOGGER_LEVEL)
    slt_formatter = logging.Formatter(LOGGER_FORMAT)
    slt_filter = logging.Filter(name=LOGGER_NAME)

    # - configure handlers - #
    slt_file_handler = logging.FileHandler(filename=LOGGER_FILE_NAME)
    slt_gui_handler = GuiStreamHandler(LOGGER_GUI_SIGNAL)

    # - add filters and format to the handlers - #
    slt_file_handler.setFormatter(slt_formatter)
    slt_gui_handler.setFormatter(slt_formatter)
    slt_file_handler.addFilter(slt_filter)
    slt_gui_handler.addFilter(slt_filter)

    # - add the handlers to the logger - #
    slt_logger.addHandler(slt_file_handler)
    slt_logger.addHandler(slt_gui_handler)

