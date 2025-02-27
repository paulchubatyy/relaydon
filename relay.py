import os
import environs
import feedparser
import logging
from time import struct_time
from datetime import datetime
from csv import DictReader, DictWriter

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from threading import Lock


env = environs.Env()
env.read_env()

# Important part: feed url and last update
feed_data: dict[str, datetime] = {}

LOG_LEVEL = env.str('LOG_LEVEL', default='INFO').upper()
INTERVAL_SECONDS = env.int('INTERVAL_SECONDS', default=900)
DATA_FILE = env.str('DATA_FILE', default='data.csv')
CSV_DELIMITER = env.str('CSV_DELIMITER', default=',')


def struct_to_datetime(time_struct: struct_time) -> datetime:
    return datetime.fromtimestamp(datetime(*time_struct[:6]).timestamp())


data_lock = Lock()

logging.basicConfig(level=LOG_LEVEL)
log = logging.getLogger(__file__)


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
        for entry in feed.entries:
            published_dt = struct_to_datetime(entry.published_parsed)
            if published_dt <= feed_data[feed_url]:
                log.debug(f"Skipping old entry {entry.title} that was published on {published_dt}")
                continue
            log.info(f"New entry in feed {feed_url}")
            log.info(f"{entry.title} published on {published_dt}")

            publish_entry(entry)
            feed_data[feed_url] = published_dt
            write_data()
    except Exception as e:
        log.error(f"Sour feed {feed_url}: {e}")


def publish_entry(entry):
    log.info(f"Publishing entry {entry.title}")

def main():
    try:
        if not os.path.exists(DATA_FILE):
            raise FileNotFoundError(f"Data file {DATA_FILE} not found")
        if not os.access(DATA_FILE, os.R_OK):
            raise PermissionError(f"Data file {DATA_FILE} is not readable")
        if not os.access(DATA_FILE, os.W_OK):
            raise PermissionError(f"Data file {DATA_FILE} is not writable")

        log.info("Starting relay...")
        read_data()
        log.info(f"{DATA_FILE} loaded, found {len(feed_data)} feeds")

        scheduler = BlockingScheduler(
            executors={
                'default': ThreadPoolExecutor(10),
            }
        )
        for feed_url, last_update in feed_data.items():
            log.info(f"Adding feed {feed_url}, last update {last_update}")
            scheduler.add_job(fetch_feed, 'interval', args=[feed_url], seconds=INTERVAL_SECONDS)
        log.info("Starting scheduler")
        scheduler.start()
    except KeyboardInterrupt:
        log.info("Shutting down the relay")
        scheduler.shutdown()
        write_data()
    except OSError as e:
        log.exception(f"Sour data file: {e}")


if __name__ == '__main__':
    main()
