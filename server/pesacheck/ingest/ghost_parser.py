import json
import hashlib
import logging
import random
import time
from copy import deepcopy
from urllib.parse import urlparse

from datetime import datetime

from superdesk.errors import ParserError
from superdesk.etree import parse_html
from superdesk.metadata.utils import generate_guid
from superdesk.io.feed_parsers import FileFeedParser
from superdesk.io.registry import register_feed_parser
from superdesk.media.renditions import update_renditions
from superdesk.metadata.item import FORMAT, GUID_FIELD, GUID_TAG, ITEM_TYPE, CONTENT_TYPE, FORMATS
from superdesk.utc import utcnow


logger = logging.getLogger(__name__)

# bytes to peek at for fast can_parse check
_PEEK_SIZE = 512
_IMAGE_FETCH_RETRIES = 4
_IMAGE_FETCH_TIMEOUT = 20
_IMAGE_FETCH_BASE_BACKOFF_SECONDS = 0.75
_IMAGE_FETCH_JITTER_SECONDS = 0.25
_IMAGE_FETCH_SUCCESS_THROTTLE_SECONDS = 0.1
_IMAGE_FETCH_MIN_INTERVAL_SECONDS = 1.25
_IMAGE_FETCH_FAILURE_COOLDOWN_SECONDS = 3.0

# Medium CDN is the problematic source in current imports, so use a slower policy there.
_MEDIUM_FETCH_RETRIES = 10
_MEDIUM_FETCH_BASE_BACKOFF_SECONDS = 2.5
_MEDIUM_FETCH_MIN_INTERVAL_SECONDS = 3.0
_MEDIUM_FETCH_FAILURE_COOLDOWN_SECONDS = 8.0

_IMAGE_FETCH_HEADERS = {
    # Some CDNs are strict about clients and may reject default python user-agent.
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) GhostIngest/1.0",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://medium.com/",
}


class GhostParser(FileFeedParser):
    """
    Feed Parser for parsing Ghost CMS JSON export files.

    Expects the standard Ghost export format (db[0].data.posts etc.).
    Only published posts of type 'post' are imported.
    """

    NAME = "ghost"
    label = "Ghost CMS Parser"

    def __init__(self):
        super().__init__()
        self._last_image_fetch_ts = 0.0
        self._image_assoc_cache = {}

    def _is_medium_cdn_url(self, url):
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            return False
        return "medium.com" in host

    def _get_fetch_policy(self, url):
        if self._is_medium_cdn_url(url):
            return {
                "retries": _MEDIUM_FETCH_RETRIES,
                "base_backoff": _MEDIUM_FETCH_BASE_BACKOFF_SECONDS,
                "min_interval": _MEDIUM_FETCH_MIN_INTERVAL_SECONDS,
                "failure_cooldown": _MEDIUM_FETCH_FAILURE_COOLDOWN_SECONDS,
            }

        return {
            "retries": _IMAGE_FETCH_RETRIES,
            "base_backoff": _IMAGE_FETCH_BASE_BACKOFF_SECONDS,
            "min_interval": _IMAGE_FETCH_MIN_INTERVAL_SECONDS,
            "failure_cooldown": _IMAGE_FETCH_FAILURE_COOLDOWN_SECONDS,
        }

    def _sleep_before_next_fetch(self, min_interval):
        elapsed = time.monotonic() - self._last_image_fetch_ts
        wait_for = min_interval - elapsed
        if wait_for > 0:
            # Pace all fetches (not just retries) to avoid hammering remote CDN endpoints.
            time.sleep(wait_for + random.uniform(0, _IMAGE_FETCH_JITTER_SECONDS))

    def _mark_fetch_done(self):
        self._last_image_fetch_ts = time.monotonic()

    def can_parse(self, file_path):
        try:
            with open(file_path, "rb") as f:
                head = f.read(_PEEK_SIZE).decode("utf-8", errors="ignore").strip()
            return head.startswith("{") and '"db"' in head
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Image helpers — same pattern as MediumParser
    # ------------------------------------------------------------------

    def _generate_image_guid(self, url):
        guid_hash = hashlib.sha1(url.encode("utf8")).hexdigest()
        return generate_guid(type=GUID_TAG, id=guid_hash + "-image")

    def _fetch_renditions_with_retry(self, association, url):
        if url in self._image_assoc_cache:
            cached = self._image_assoc_cache[url]
            association.update(deepcopy(cached))
            return

        policy = self._get_fetch_policy(url)
        last_error = None
        for attempt in range(1, policy["retries"] + 1):
            try:
                self._sleep_before_next_fetch(policy["min_interval"])
                update_renditions(
                    association,
                    url,
                    None,
                    request_kwargs={
                        "timeout": _IMAGE_FETCH_TIMEOUT,
                        "headers": _IMAGE_FETCH_HEADERS,
                    },
                )
                self._mark_fetch_done()
                if _IMAGE_FETCH_SUCCESS_THROTTLE_SECONDS > 0:
                    time.sleep(_IMAGE_FETCH_SUCCESS_THROTTLE_SECONDS)

                self._image_assoc_cache[url] = {
                    "renditions": deepcopy(association.get("renditions")),
                    "mimetype": association.get("mimetype"),
                    "filemeta": deepcopy(association.get("filemeta")),
                    "filemeta_json": deepcopy(association.get("filemeta_json")),
                }
                return
            except Exception as ex:
                self._mark_fetch_done()
                last_error = ex
                if attempt == policy["retries"]:
                    break

                delay = (policy["base_backoff"] * attempt) + random.uniform(0, _IMAGE_FETCH_JITTER_SECONDS)
                logger.warning(
                    "Image fetch failed for %s (attempt %s/%s), retrying in %.2fs: %s",
                    url,
                    attempt,
                    policy["retries"],
                    delay,
                    ex,
                )
                time.sleep(delay)

        if policy["failure_cooldown"] > 0:
            # After exhausting retries, cool down before the next image to reduce cascading failures.
            time.sleep(policy["failure_cooldown"] + random.uniform(0, _IMAGE_FETCH_JITTER_SECONDS))

        raise last_error

    def _add_image(self, item, url, alt_text="", description_text="", is_featured=False):
        associations = item.setdefault("associations", {})
        association = {
            ITEM_TYPE: CONTENT_TYPE.PICTURE,
            GUID_FIELD: self._generate_image_guid(url),
            "headline": item.get("headline", ""),
            "alt_text": alt_text,
            "description_text": description_text,
        }
        self._fetch_renditions_with_retry(association, url)

        if is_featured and "featuremedia" not in associations:
            key = "featuremedia"
        elif "featuremedia" not in associations:
            key = "featuremedia"
        else:
            key = "embedded" + str(len(associations) - 1)

        associations[key] = association

    def _parse_feature_image(self, item, post):
        url = post.get("feature_image")
        if url:
            try:
                self._add_image(item, url, is_featured=True)
            except Exception as e:
                logger.warning("Failed to fetch feature_image %s: %s", url, e)

    def _parse_inline_images(self, item, html):
        if not html:
            return
        try:
            root = parse_html(html, "html")
        except Exception as e:
            logger.warning("Failed to parse HTML for inline images: %s", e)
            return

        for img in root.xpath(".//img"):
            try:
                src = img.get("src")
                if not src:
                    continue

                alt_text = img.get("alt") or ""
                description_text = ""

                parent = img.getparent()
                if parent is not None and parent.tag == "figure":
                    figcaption = parent.find(".//figcaption")
                    if figcaption is not None:
                        description_text = (
                            figcaption.text_content()
                            if hasattr(figcaption, "text_content")
                            else (figcaption.text or "")
                        ).strip()

                self._add_image(item, src, alt_text, description_text)
            except Exception as e:
                logger.warning("Failed to parse inline image %s: %s", img.get("src", "unknown"), e)

    # ------------------------------------------------------------------
    # Date parsing
    # ------------------------------------------------------------------

    def _parse_date(self, value):
        if not value:
            return utcnow()
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(value, fmt)
            except (ValueError, TypeError):
                continue
        raise ValueError("Unrecognised date format: %r" % value)

    # ------------------------------------------------------------------
    # Single post → Superdesk item
    # ------------------------------------------------------------------

    def _parse_post(self, post, authors_by_post, tags_by_post):
        post_id = post.get("id", "")

        authors = sorted(authors_by_post.get(post_id, []), key=lambda x: x["sort_order"])
        byline = ", ".join(a["name"] for a in authors if a.get("name"))

        tags = sorted(tags_by_post.get(post_id, []), key=lambda x: x["sort_order"])
        keywords = [t["name"] for t in tags if t.get("name")]

        firstcreated = self._parse_date(post.get("created_at"))
        versioncreated = self._parse_date(post.get("published_at") or post.get("updated_at"))

        html = post.get("html") or ""

        item = {
            ITEM_TYPE: CONTENT_TYPE.TEXT,
            GUID_FIELD: post.get("uuid") or generate_guid(type=GUID_TAG),
            FORMAT: FORMATS.HTML,
            "headline": post.get("title") or "",
            "abstract": post.get("custom_excerpt") or "",
            "slugline": post.get("slug") or "",
            "byline": byline,
            "keywords": keywords,
            "body_html": html,
            "source": "Ghost",
            "firstcreated": firstcreated,
            "versioncreated": versioncreated,
        }

        locale = post.get("locale")
        if locale:
            item["language"] = locale

        self._parse_feature_image(item, post)
        self._parse_inline_images(item, html)

        return item

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def parse(self, file_path, provider=None):
        """Parse a Ghost JSON export file and return a list of Superdesk items."""
        self._image_assoc_cache = {}
        self._last_image_fetch_ts = 0.0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            db_data = data["db"][0]["data"]
            posts = db_data.get("posts", [])
            users = db_data.get("users", [])
            tags = db_data.get("tags", [])
            posts_authors = db_data.get("posts_authors", [])
            posts_tags = db_data.get("posts_tags", [])

        except Exception as ex:
            raise ParserError.parseFileError(file_path, ex)

        # build lookup dicts
        users_by_id = {u["id"]: u for u in users}
        tags_by_id = {t["id"]: t for t in tags}

        authors_by_post = {}
        for pa in posts_authors:
            pid = pa.get("post_id")
            uid = pa.get("author_id")
            user = users_by_id.get(uid)
            if pid and user:
                authors_by_post.setdefault(pid, []).append(
                    {
                        "name": user.get("name", ""),
                        "sort_order": pa.get("sort_order", 0),
                    }
                )

        tags_by_post = {}
        for pt in posts_tags:
            pid = pt.get("post_id")
            tid = pt.get("tag_id")
            tag = tags_by_id.get(tid)
            if pid and tag:
                tags_by_post.setdefault(pid, []).append(
                    {
                        "name": tag.get("name", ""),
                        "sort_order": pt.get("sort_order", 0),
                    }
                )

        items = []
        for post in posts:
            if post.get("status") != "published" or post.get("type") != "post":
                continue
            try:
                items.append(self._parse_post(post, authors_by_post, tags_by_post))
            except Exception as ex:
                logger.warning("Failed to parse Ghost post %s: %s", post.get("id"), ex)

        return items


register_feed_parser(GhostParser.NAME, GhostParser())
