import os
import logging

from superdesk.errors import ParserError
from superdesk.io.feeding_services.file_service import FileFeedingService
from superdesk.io.registry import register_feeding_service
from superdesk.notification import push_notification
from superdesk.utils import get_sorted_files, FileSortAttributes


logger = logging.getLogger(__name__)

BATCH_SIZE = 10


class GhostFeedingService(FileFeedingService):
    """
    Feeding Service for Ghost CMS JSON export files.

    Extends the standard file feeding service to yield ingested items
    in batches of BATCH_SIZE, making large Ghost dumps manageable.
    """

    NAME = "ghost_file"
    label = "Ghost CMS file feed"

    def _update(self, provider, update):
        self.provider = provider
        self.path = provider.get("config", {}).get("path", None)

        if not self.path:
            logger.warning(
                "Ghost Feeding Service %s is configured without path. Please check the configuration",
                provider["name"],
            )
            return []

        for filename in get_sorted_files(self.path, sort_by=FileSortAttributes.created):
            last_updated = None
            try:
                file_path = os.path.join(self.path, filename)
                if not os.path.isfile(file_path):
                    continue

                last_updated = self.get_last_updated(file_path)

                if not self.is_latest_content(last_updated, provider.get("last_updated")):
                    self.move_file(self.path, filename, provider=provider, success=False)
                    continue

                if self.is_empty(file_path):
                    logger.info("Ignoring empty file %s", filename)
                    continue

                parser = self.get_feed_parser(provider, file_path)
                if not parser.can_parse(file_path):
                    logger.info("Skipping non-Ghost file %s", filename)
                    continue

                all_items = parser.parse(file_path, provider)

                failed = False
                for i in range(0, len(all_items), BATCH_SIZE):
                    batch = all_items[i : i + BATCH_SIZE]
                    failed = yield batch
                    if failed:
                        break

                self.move_file(self.path, filename, provider=provider, success=not failed)

            except Exception as ex:
                if last_updated and self.is_old_content(last_updated):
                    self.move_file(self.path, filename, provider=provider, success=False)
                raise ParserError.parseFileError("{}-{}".format(provider["name"], self.NAME), filename, ex, provider)

        push_notification("ingest:update")


register_feeding_service(GhostFeedingService)
