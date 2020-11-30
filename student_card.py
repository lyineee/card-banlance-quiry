import json
import logging
import os
import time

import requests as rq
from redis import StrictRedis

logger = logging.getLogger(__file__)


class CardBalanceQuiry(object):

    balance_url = "http://jhzf.upc.edu.cn:20081/wechat/callinterface/getCardInfo.html"
    history_url = "http://jhzf.upc.edu.cn:20081/wechat/callinterface/queryHisTotal.html"
    today = None
    balance = None
    errmsg = ""
    cookies = dict()

    def __init__(self, student_id, password, card_no, xxbh):
        self.student_id = student_id
        self.password = password
        self.card_no = card_no
        self.xxbh = xxbh
        # Connect to redis
        self.redis = StrictRedis(
            host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=0
        )

    def date(self):
        return time.strftime("%Y%m%d", time.localtime())

    def quiry_balance(self, retry: int = 3) -> float:
        try:
            form_data = {
                "sno": self.student_id,
                "xxbh": self.xxbh,  # key
                "idtype": "acc",
                "id": self.card_no,
            }
            resp = rq.post(self.balance_url, form_data)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    self.errmsg = "返回格式错误"
                    logger.warning(
                        "Error json format when quiry balance, response: {}".format(
                            resp.content
                        )
                    )
                    return -1
                if data["retcode"] != "0":
                    self.errmsg = data["errmsg"]
                    return -1
                self.balance = float(data["card"][0]["db_balance"]) / 100

        except Exception as e:
            logger.warning("quiry balance error, msg: {}".format(e))
            raise

        return self.balance

    def quiry_today(self, reset=False) -> float:
        """
        Get today's usage
        """
        today = 0
        current_page = 1
        form_data = {
            "sno": self.student_id,
            "xxbh": self.xxbh,  # key
            "idtype": "acc",
            "id": self.card_no,
            "curpage": current_page,
            "pagesize": 10,
            "account": self.card_no,
            "acctype": "",
            "query_start": self.date(),
            "query_end": self.date(),
        }
        while True:
            resp = rq.post(self.history_url, form_data)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    self.errmsg = "返回格式错误"
                    logger.warning(
                        "Error json format when quiry balance, response: {}".format(
                            resp.content
                        )
                    )
                    return -1
                if data["retcode"] != "0":
                    self.errmsg = data["errmsg"]
                    return -1
                for item in data["total"]:
                    if item["sign_tranamt"].find("-") != -1:
                        today += float(item["tranamt"]) / 100
                if data["nextpage"] == 0:
                    break
                current_page += 1
            return today

    def redis_update(self):
        balance = self.quiry_balance()
        today = self.quiry_today()
        timestamp = int(time.time())
        self.redis.hset(
            self.student_id,
            mapping={"balance": balance, "today": today, "timestamp": timestamp},
        )
        # self.redis.hmset(  # compatible for windows
        #     self.student_id,
        #     mapping={"balance": balance, "today": today, "timestamp": timestamp},
        # )


def test():
    id = os.getenv("STUDENT_ID")
    password = os.getenv("PASSWORD")
    card_no = os.getenv("CARD_NO")
    xxbh = os.getenv("XXBH")
    logger.info(
        "Student ID is {}, password is {}, xxbh is {}".format(id, password, xxbh)
    )
    test_quiry = CardBalanceQuiry(id, password, card_no, xxbh)
    balance = test_quiry.quiry_balance()
    if balance == -1:
        print(test_quiry.errmsg)
    print(balance)
    today = test_quiry.quiry_today()
    if today == -1:
        print(test_quiry.errmsg)
    print(today)
    test_quiry.redis_update()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", logging.INFO))
    logger.setLevel(os.getenv("LOG_LEVEL", logging.INFO))
    test()
