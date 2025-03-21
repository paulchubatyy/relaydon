import os
import environs
import feedparser
import logging
import time
import signal
from time import struct_time
from datetime import datetime, timedelta
from csv import DictReader, DictWriter

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from mastodon import Mastodon
from threading import Lock, Thread

# Read the configuration from env variables
env = environs.Env()
env.read_env()

# Configuration itself
TZ = env.str('TZ', default='')
LOG_LEVEL = env.str('LOG_LEVEL', default='INFO').upper()
INTERVAL_SECONDS = env.int('INTERVAL_SECONDS', default=900)
DATA_FILE = env.str('DATA_FILE', default='data.csv')
CSV_DELIMITER = env.str('CSV_DELIMITER', default=',')
MASTODON_ACCESS_TOKEN = env.str('MASTODON_ACCESS_TOKEN', default=None)
MASTODON_URL = env.str('MASTODON_URL', default=None)
MASTODON_VISIBILITY = env.str('MASTODON_VISIBILITY', default='unlisted')
MASTODON_APPLICATION_NAME = env.str('MASTODON_APPLICATION_NAME', default='RelayDon')
GIT_SHA = env.str('GIT_SHA', default='development')

# Logging setup
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(pathname)s:%(lineno)d - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__file__)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

# Important part: feed url and last update
feed_data: dict[str, datetime] = {}
# Thread lock for data writes
data_lock = Lock()

# Convert feedparser time struct to datetime
def struct_to_datetime(time_struct: struct_time) -> datetime:
    return datetime.fromtimestamp(datetime(*time_struct[:6]).timestamp())

# Configuration assumptions
mastodon = Mastodon(
    access_token=MASTODON_ACCESS_TOKEN,
    api_base_url=MASTODON_URL
) if MASTODON_ACCESS_TOKEN and MASTODON_URL else None

# Test mode?
TEST_MODE = mastodon is None


def read_data():
    reader = DictReader(open(DATA_FILE, "r"), fieldnames=["feed_url", "last_update"], delimiter=CSV_DELIMITER)
    for row in reader:
        try:
            feed_data[row["feed_url"]] = datetime.fromisoformat(row["last_update"])
        except (TypeError, ValueError):  # sour date
            feed_data[row["feed_url"]] = datetime.now()


def write_data():
    with data_lock, open(DATA_FILE, "w") as f:
        writer = DictWriter(f, fieldnames=["feed_url", "last_update"], delimiter=CSV_DELIMITER)
        for feed_url, last_update in feed_data.items():
            writer.writerow({"feed_url": feed_url, "last_update": last_update.isoformat()})


def fetch_feed(feed_url: str):
    try:
        feed = feedparser.parse(feed_url)
        log.info(f"Fetching feed {feed_url}")
        for entry in feed.entries:
            published_dt = struct_to_datetime(entry.published_parsed)

            if not TEST_MODE and published_dt <= feed_data[feed_url]:
                log.debug(f"Skipping old entry {entry.title} that was published on {published_dt}")
                continue

            log.debug(f"New entry in feed {feed_url}")
            log.debug(f"{entry.title} published on {published_dt}")

            publish_entry(entry)

            feed_data[feed_url] = published_dt
            write_data()
    except Exception as e:
        log.error(f"Sour feed {feed_url}: {e}")


def publish_entry(entry):
    log.debug(f"Publishing entry {entry.title}")

    if TEST_MODE:
        log.warning(f"{entry.summary}\n\n{entry.link}")
        return

    post = mastodon.status_post(
        status=f"{entry.summary}\n\n{entry.link}",
        visibility=MASTODON_VISIBILITY,
        # application=MASTODON_APPLICATION_NAME,
    )

    log.info(f"Entry {entry.title} published to {post.url}"
             f" at {post.created_at}")


def check_data_file(filepath: str) -> None:
    """Validate data file existence and permissions."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Data file {filepath} not found")
    if not (os.access(filepath, os.R_OK) and os.access(filepath, os.W_OK)):
        raise PermissionError(f"Data file {filepath} needs read and write permissions")

def main():
    try:
        if TZ:
            time.tzset()
            log.warning(f"Set timezone to: {TZ}")
        if TEST_MODE:
            log.warning("Running in test mode")

        check_data_file(DATA_FILE)

        log.info(f"Starting RelayDon version {GIT_SHA}")
        read_data()
        log.info(f"{DATA_FILE} loaded, found {len(feed_data)} feeds")

        scheduler = BlockingScheduler(
            executors={
                'default': ThreadPoolExecutor(10),
            }
        )
        for feed_url, last_update in feed_data.items():
            log.info(f"Adding feed {feed_url}, last update {last_update}")
            thread = Thread(target=fetch_feed, args=(feed_url,))
            thread.start()
            thread.join()
            scheduler.add_job(fetch_feed, 'interval', args=[feed_url], seconds=INTERVAL_SECONDS)
            log.info(f"will fetch feed {feed_url} on {datetime.now() + timedelta(seconds=INTERVAL_SECONDS)}")
        scheduler.start()
    except KeyboardInterrupt:
        log.info("Shutting down the relay")
        scheduler.shutdown()
        write_data()
    except OSError as e:
        log.exception(f"Sour data file: {e}")


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda signum, frame: write_data())
    main()
