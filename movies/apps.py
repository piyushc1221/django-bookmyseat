import os
import threading
import time

from django.apps import AppConfig
from django.conf import settings
from django.db import close_old_connections
from django.db.utils import OperationalError, ProgrammingError


_reservation_scheduler_started = False


class MoviesConfig(AppConfig):
    name = 'movies'

    def ready(self):
        global _reservation_scheduler_started

        if _reservation_scheduler_started:
            return

        if settings.DEBUG and os.environ.get("RUN_MAIN") != "true":
            return

        _reservation_scheduler_started = True
        thread = threading.Thread(target=self.release_expired_reservations, daemon=True)
        thread.start()

    def release_expired_reservations(self):
        while True:
            time.sleep(30)
            close_old_connections()

            try:
                from .reservations import release_expired_reservations
                from .payments import expire_pending_payments

                release_expired_reservations()
                expire_pending_payments()
            except (OperationalError, ProgrammingError):
                pass
