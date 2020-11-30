from datetime import date
import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from student_card import CardBalanceQuiry

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", logging.DEBUG))
logger = logging.getLogger(__file__)
logger.setLevel(os.getenv("LOG_LEVEL", logging.DEBUG))

default_update_cron = {"second": "*", "minute": "*/20", "hour": "*"}
day_begin_update = {"second": "0", "minute": "0", "hour": "0"}

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


def update_card_info():
    try:
        updater.redis_update()
    except Exception as e:
        logger.exception("Error occur, detail: {}".format(e))


# First run
update_card_info()
logger.info("First run to get info")

scheduler.add_job(
    update_card_info, trigger="cron", id="info_updater", **default_update_cron
)
scheduler.add_job(update_start, trigger="cron", **day_begin_update)
scheduler.add_job(update_job, trigger="cron", minute="*/5")
scheduler.start()
