import environs
import feedparser
import logging
from datetime import datetime
from csv import DictReader, DictWriter

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from threading import Lock


env = environs.Env()
env.read_env()

feed_data = {}

RSS_FEEDS = env.list('RSS_FEEDS', default=[])
INTERVAL_SECONDS = env.int('INTERVAL_SECONDS', default=900)
DATA_FILE = env.str('DATA_FILE', default='data.txt')

data_lock = Lock()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__file__)


def read_data():
    reader = DictReader(open(DATA_FILE, "r"), fieldnames=["feed_url", "last_update"], delimiter="|")
    for row in reader:
        try:
            feed_data[row["feed_url"]] = datetime.fromisoformat(row["last_update"])
        except Exception:
            feed_data[row["feed_url"]] = datetime.now()


def write_data():
    with data_lock, DictWriter(open(DATA_FILE, "w"), fieldnames=["feed_url", "last_update"], delimiter="|") as f:
        for feed_url, last_update in feed_data.items():
            f.writerow({"feed_url": feed_url, "last_update": last_update.isoformat()})
        f.flush()


def fetch_feed(feed_url: str):
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if entry.date_parsed <= feed_data[feed_url]:
                continue
            log.info(f"New entry in feed {feed_url}")
            log.info(f"{entry.title} published on {entry.published_parsed}")
    except Exception as e:
        log.error(f"Sour feed {feed_url}: {e}")


def main():
    try:
        feed_data = read_data()
        scheduler = BlockingScheduler(
            executors={
                'default': ThreadPoolExecutor(10),
            }
        )
        for feed_url, last_update in feed_data.items():
            scheduler.add_job(fetch_feed, 'interval', args=[feed_url], seconds=INTERVAL_SECONDS)
        scheduler.start()
    except KeyboardInterrupt:
        log.info("Shutting down the relay")
        scheduler.shutdown()
        write_data()


if __name__ == '__main__':
    main()
