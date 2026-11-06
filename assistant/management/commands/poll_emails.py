import time

from django.core.management.base import BaseCommand

from assistant.emailer import process_inbox


class Command(BaseCommand):
    help = "Read unread Gmail messages and reply with the AI. Use --loop to keep running."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Keep checking forever")
        parser.add_argument("--interval", type=int, default=60, help="Seconds between checks (default 60)")

    def handle(self, *args, **options):
        while True:
            try:
                count = process_inbox()
                self.stdout.write(f"Checked inbox: {count} message(s) handled")
            except Exception as exc:
                self.stderr.write(f"Inbox check failed: {exc}")
                if not options["loop"]:
                    raise
            if not options["loop"]:
                break
            time.sleep(options["interval"])
