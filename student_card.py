import base64
import json
import logging
import os
import time
from json.decoder import JSONDecodeError

import requests as rq
from redis import StrictRedis

logger = logging.getLogger(__file__)


class CardBalanceQuiry(object):

    balance_url = "https://wvpn.upc.edu.cn/http-20086/77726476706e69737468656265737421f5f4408e23367f1e6b188ae29d51367beb72/User/GetCardInfoByAccountNoParm"
    history_url = "https://wvpn.upc.edu.cn/http-20086/77726476706e69737468656265737421f5f4408e23367f1e6b188ae29d51367beb72/Report/GetMyBill"
    today = None
    balance = None
    cookies = dict()

    def __init__(self, student_id, password, card_no):
        self.student_id = student_id
        self.password = password
        self.card_no = card_no
        # Connect to redis
        self.redis = StrictRedis(
            host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=0
        )
        # Init obj
        self.account = Login(self.student_id, self.password)

    def date(self):
        return time.strftime("%Y-%m-%d", time.localtime())

    def quiry_balance(self, retry=3):
        cookies = self.get_cookies()
        try:
            for _ in range(retry):
                res = rq.post(
                    self.balance_url,
                    cookies=cookies,
                    data={"json": "ture"},
                )
                try:
                    quiry_json = json.loads(res.json()["Msg"])
                except json.decoder.JSONDecodeError as e:
                    logger.info("Wvpn ticket Expired, msg: {}".format(e))
                    cookies = self.get_cookies(refresh=True)
                    continue
                if not res.json()["IsSucceed"]:
                    self.balance = (
                        int(quiry_json["query_card"]["card"][0]["db_balance"]) / 100
                    )
                    break
                else:
                    logger.info("Wvpn connection outdated, try to refresh")
                    cookies = self.get_cookies(refresh=True)

        except Exception as e:
            logger.warning("quiry balance error, msg: {}".format(e))
            raise

        return self.balance

    def quiry_today(self, retry=3):  # Api deprecated
        cookies = self.get_cookies()
        today = 0
        for _ in range(retry):
            try:

                res = rq.post(
                    self.history_url,
                    cookies=cookies,
                    data={
                        "sdate": self.date(),
                        "edate": self.date(),
                        "account": self.card_no,
                    },
                )
                for i in res.json()["rows"]:
                    val = i["TRANAMT"]
                    if val < 0:
                        today += val
                break
            except JSONDecodeError:
                # raise ConnectionRefusedError
                cookies = self.get_cookies(refresh=True)
            except Exception as e:
                logger.warning("quiry history error, msg: {}".format(e))
                cookies = self.get_cookies(refresh=True)
                # raise
        return today

    def get_cookies(self, refresh=False):
        if not refresh:
            wengine_vpn_ticketwvpn_upc_edu_cn = self.redis.hmget(
                self.student_id, "wengine_vpn_ticketwvpn_upc_edu_cn"
            )[0]
            if wengine_vpn_ticketwvpn_upc_edu_cn:
                wengine_vpn_ticketwvpn_upc_edu_cn = (
                    wengine_vpn_ticketwvpn_upc_edu_cn.decode()
                )
                logger.debug(
                    "Get cache wvpn ticket {}".format(wengine_vpn_ticketwvpn_upc_edu_cn)
                )
                cookies = {
                    "wengine_vpn_ticketwvpn_upc_edu_cn": wengine_vpn_ticketwvpn_upc_edu_cn,
                }
            else:
                cookies = self.account.get_cookies()
        else:
            value = self.account.get_cookies()
            cookies = {
                "wengine_vpn_ticketwvpn_upc_edu_cn": value,
            }
        return cookies

    def redis_update(self):
        balance = self.quiry_balance()
        today = self.quiry_today()
        timestamp = int(time.time())
        self.redis.hmset(  # TODO hmset is deprecated
            self.student_id,
            {"balance": balance, "today": today, "timestamp": timestamp},
        )


def ocr(img_b64, access_token):
    base_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={}"
    headers = {"content-type": "application/x-www-form-urlencoded"}
    params = {"image": img_b64}
    resp = rq.post(base_url.format(access_token), data=params, headers=headers)
    resp_json = resp.json()
    if "words_result" in resp_json and resp_json["words_result"] != []:
        return resp_json["words_result"][0]["words"]


class Login(object):

    headers = {
        "Referer": "https://wvpn.upc.edu.cn/http-20086/77726476706e69737468656265737421f5f4408e23367f1e6b188ae29d51367beb72"
    }

    def __init__(self, card_no, password, retry=5):
        self.no = card_no
        self.pwd = password
        self.pwd_base64 = base64.b64encode(password.encode("utf-8")).decode("ascii")
        self.retry = retry
        self.cookies = {}
        self.validate_code = None
        self.wvpn_username = os.getenv("WVPN_USERNAME")
        self.wvpn_password = os.getenv("WVPN_PASSWORD")

        self.input_width = 109
        self.input_height = 41
        self.host = "https://wvpn.upc.edu.cn/http-20086/77726476706e69737468656265737421f5f4408e23367f1e6b188ae29d51367beb72/"

        # Connect to redis
        try:
            self.redis = StrictRedis(
                host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=0
            )
        except NameError as e:
            logger.error("Redis env error, msg:  {}".format(e))
            raise

    def _wvpn_cookies(self, username: str, password: str) -> dict:
        data = {"username": username, "password": password}
        resp = rq.post("https://wvpn.upc.edu.cn/do-login", data=data)
        if resp.json()["success"]:
            cookies = {
                "wengine_vpn_ticketwvpn_upc_edu_cn": resp.cookies[
                    "wengine_vpn_ticketwvpn_upc_edu_cn"
                ],
            }
            logger.info("Successfully login wvpn")
            return cookies
        else:
            logger.warning("Fail login to wvpn")

    def _get_cookies(self):
        try:
            wvpn_cookies = self._wvpn_cookies(self.wvpn_username, self.wvpn_password)
            self.cookies = wvpn_cookies
            return wvpn_cookies
        except Exception as e:
            # raise Exception('error when get cookie')
            logger.info("error when get cookie, msg: {}".format(e))
            raise

    def _get_validate_img(self) -> bytes:
        logger.debug("Start get captcha image")
        validate_code_time = str(time.time()).replace(".", "")
        validate_code_url = "{}/Login/GetValidateCode?time={}".format(
            self.host, validate_code_time
        )
        validate_code_resp = rq.get(validate_code_url, cookies=self.cookies)
        if validate_code_resp.status_code == 200:
            validate_img = validate_code_resp.content
        else:
            raise Exception("error when get validate image")
        logger.debug("successfully get captcha image")
        return validate_img

    def _get_validate_code_ocr(self, validate_img: bytes) -> str:
        """
        validate_img: Matrix format image
        """
        img_b64 = base64.b64encode(validate_img)
        result = ocr(
            img_b64,
            self.get_access_token(os.getenv("CLIENT_ID"), os.getenv("CLIENT_SECRET")),
        )
        logger.debug("Validation code is {}".format(result))
        return result

    def _login(self, no, pwd_b64, validate_code):
        post_data = {
            "sno": no,
            "pwd": pwd_b64,
            "ValiCode": validate_code,
            "remember": "1",
            "uclass": "1",
            "json": "true",
        }
        try:
            login_resp = rq.post(
                "{}Login/LoginBySnoQuery".format(self.host),
                data=post_data,
                cookies=self.cookies,
                headers=self.headers,
            )
        except Exception as e:
            logger.info("error when login, msg{}".format(e))
            raise
        resp_json = login_resp.json()
        if not resp_json["IsSucceed"]:
            raise Exception("login failed", "captcha_error")
        return self.cookies

    def get_cookies(self, retry=None) -> str:
        if not retry:
            retry = self.retry
        count = 0
        while count <= retry:
            self._get_cookies()
            val_img = self._get_validate_img()

            # code = self._get_validate_code(val_img)
            code = self._get_validate_code_ocr(val_img)  # Using ocr
            try:
                self._login(self.no, self.pwd_base64, code)
            except Exception as e:
                logger.info("Exception catch when login, msg {}".format(e))
                if len(e.args) >= 2:
                    if e.args[1] == "captcha_error":
                        logger.warning("captcha error")
                # raise
                count += 1
            else:
                break
        else:
            logger.error("Hit maximum try")
            raise Exception("Maximum try!")
        self.redis.hmset(  # TODO hmset is deprecated
            self.no,
            {
                "wengine_vpn_ticketwvpn_upc_edu_cn": self.cookies[
                    "wengine_vpn_ticketwvpn_upc_edu_cn"
                ],
            },
        )
        logger.debug("Store user {} wvpn ticket in redis".format(self.no))
        return self.cookies["wengine_vpn_ticketwvpn_upc_edu_cn"]

    def get_access_token(self, client_id, client_secret):
        base_url = "https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={}&client_secret={}"
        token = self.redis.get("client_token")
        if not token:
            logger.info("Requesting token")
            token_resp = rq.get(base_url.format(client_id, client_secret))
            resp_data = token_resp.json()
            if "error" not in resp_data:
                token = resp_data["access_token"]
                logger.debug("Successfully get token {}".format(token))
                self.redis.set("client_token", token, ex=resp_data["expires_in"])
        else:
            logger.debug("Hit cache, token is {}".format(token))
        return token


def test():
    id = os.getenv("STUDENT_ID")
    password = os.getenv("PASSWORD")
    card_no = os.getenv("CARD_NO")
    logger.info("Student ID is {}, password is {}".format(id, password))
    test_quiry = CardBalanceQuiry(id, password, card_no)
    print(test_quiry.quiry_balance())
    print(test_quiry.quiry_today())
    test_quiry.redis_update()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", logging.INFO))
    logger.setLevel(os.getenv("LOG_LEVEL", logging.INFO))
    test()

""" encrypt example using aescfb
key='wrdvpnisthebest!'
iv='wrdvpnisthebest!'

var encrypt = function (text, key, iv) {
    var textLength = text.length
    text = textRightAppend(text, 'utf8')
    var keyBytes = utf8.toBytes(key)
    var ivBytes = utf8.toBytes(iv)
    var textBytes = utf8.toBytes(text)
    var aesCfb = new AesCfb(keyBytes, ivBytes, 16)
    var encryptBytes = aesCfb.encrypt(textBytes)
    return hex.fromBytes(ivBytes) + hex.fromBytes(encryptBytes).slice(0, textLength * 2)
}
"""
