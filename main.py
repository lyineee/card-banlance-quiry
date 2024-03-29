import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from redis import Redis

from free_class import update_class
from student_card import CardBalanceQuiry

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", logging.DEBUG))
logger = logging.getLogger(__file__)
logger.setLevel(os.getenv("LOG_LEVEL", logging.DEBUG))

default_update_cron = {"second": "*", "minute": "*/20", "hour": "*"}
day_begin_update = {"second": "0", "minute": "0", "hour": "0"}
day_after_update = {"second": "0", "minute": "0", "hour": "5"}

scheduler = BlockingScheduler()
updater = CardBalanceQuiry(
    os.getenv("STUDENT_ID"),
    os.getenv("PASSWORD"),
    os.getenv("CARD_NO"),
    os.getenv("XXBH"),
)


def update_job():
    # TODO dynamic update config
    # logging.debug('Scanning changes')
    pass


def update_start():
    """
    Run once a day to update today's usage.
    """
    updater.quiry_today(reset=True)


def update_morning():
    update_class(db)


def update_card_info():
    try:
        updater.redis_update()
    except Exception as e:
        logger.exception("Error occur, detail: {}".format(e))


# First run
db = Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=0)
update_class(db)
update_card_info()
logger.info("First run to get info")

scheduler.add_job(
    update_card_info, trigger="cron", id="info_updater", **default_update_cron
)
scheduler.add_job(update_start, trigger="cron", **day_begin_update)
scheduler.add_job(update_morning, trigger="cron", **day_after_update)
scheduler.add_job(update_job, trigger="cron", minute="*/5")
scheduler.start()
