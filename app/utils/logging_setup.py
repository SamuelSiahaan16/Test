import logging


class CheckedFileHandler(logging.FileHandler):
    """Standard logging normally swallows disk errors; surface them to runner."""
    def handleError(self, record):
        raise OSError('Gagal menulis log; periksa kapasitas disk dan izin folder')
