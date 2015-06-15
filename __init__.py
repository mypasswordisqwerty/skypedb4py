from skype import Skype

import logging

class NullHandler(logging.Handler):
    def emit(self, record):
        pass
# Suppress the "No handlers could be found for logger (...)" message.
logging.getLogger('Skype4Py').addHandler(NullHandler())