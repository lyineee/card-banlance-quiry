import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from student_card import CardBanlanceQuiry

load_dotenv()
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__file__)

default_update_cron = {"second": "*", "minute": "*/20", "hour": "*"}

scheduler = BlockingScheduler()
updater = CardBanlanceQuiry(
    os.getenv("STUDENT_ID"), os.getenv("PASSWORD"), os.getenv("CARD_NO")
)


def update_job():
    # TODO dynamic update config
    # logging.debug('Scanning changes')
    pass


def update_card_info():
    try:
        updater.redis_update()
    except Exception as e:
        logger.error("Error occur, detail: {}".format(e))
        logger.exception()


# First run
update_card_info()
logger.info('First run to get info')

scheduler.add_job(
    update_card_info, trigger="cron", id="info_updater", **default_update_cron
)
scheduler.add_job(update_job, trigger="cron", minute="*/5")
scheduler.start()
