import base64
import json
import os
import time

import cv2
import numpy as np
import requests as rq
import logging
from dotenv import load_dotenv
from redis import StrictRedis

# import tensorflow as tf
load_dotenv()
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
logger = logging.getLogger(__file__)
logging.basicConfig(level=logging.INFO)
logger.setLevel(logging.DEBUG)


def ocr(img_b64, access_token):
    base_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={}"
    headers = {"content-type": "application/x-www-form-urlencoded"}
    params = {"image": img_b64}
    resp = rq.post(base_url.format(access_token), data=params, headers=headers)
    resp_json = resp.json()
    if "words_result" in resp_json:
        return resp_json["words_result"][0]["words"]


class Login(object):

    headers = {
        "Host": "ecardfw.upc.edu.cn:20086",
        "Proxy-Connection": "keep-alive",
        "Content-Length": "72",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "http://ecardfw.upc.edu.cn:20086",
        "Referer": "http://ecardfw.upc.edu.cn:20086/",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en-US;q=0.7,en;q=0.6,fi;q=0.5",
    }

    def __init__(self, card_no, password, retry=5):
        self.no = card_no
        self.pwd = password
        self.pwd_base64 = base64.b64encode(password.encode("utf-8")).decode("ascii")
        self.retry = retry
        self.cookies = {}
        self.validate_code = None

        self.input_width = 109
        self.input_height = 41

        # Connect to redis
        try:
            self.redis = StrictRedis(
                host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=0
            )
        except NameError as e:
            logger.error("Redis env error, msg:  {}".format(e))
            raise

        # load keras model
        # print("start loading keras model...")
        # try:
        #     self.model = tf.keras.models.load_model("./result.h5")
        # except Exception as e:
        #     # raise Exception('error when load model')
        #     print("error when load model")
        #     raise
        # print("successfully load keras model")

    def _get_cookies(self):
        try:
            resp = rq.get("http://ecardfw.upc.edu.cn:20086/")
            self.cookies = {"ASP.NET_SessionId": resp.cookies["ASP.NET_SessionId"]}
        except Exception as e:
            # raise Exception('error when get cookie')
            logger.info("error when get cookie, msg: {}".format(e))
            raise

    def _get_validate_img(self):
        logger.debug("Start get captcha image")
        validate_code_time = str(time.time()).replace(".", "")
        validate_code_url = (
            "http://ecardfw.upc.edu.cn:20086/Login/GetValidateCode?time={}".format(
                validate_code_time
            )
        )
        validate_code_resp = rq.get(validate_code_url, cookies=self.cookies)
        if validate_code_resp.status_code == 200:
            with open("./validate_code_tmp.jpg", "wb") as f:
                f.write(validate_code_resp.content)
                f.flush()
                validate_img = cv2.imread(f.name)
            os.remove("./validate_code_tmp.jpg")
        else:
            raise Exception("error when get validate image")
        logger.debug("successfully get captcha image")
        return validate_img

    def _get_validate_code_ocr(self, validate_img) -> str:
        img_bytes = cv2.imencode(".jpg", validate_img)[1].tostring()
        img_b64 = base64.b64encode(img_bytes)
        result = ocr(img_b64, self.get_access_token(client_id, client_secret))
        logger.debug("Validation code is {}".format(result))
        return result

    # def _get_validate_code(self, validate_img) -> int:
    #     validate_img = cv2.resize(
    #         validate_img, (self.input_width, self.input_height)
    #     ).reshape((1, self.input_height, self.input_width, 3))
    #     print("start get code")
    #     time.sleep(1)
    #     pre = self.model.predict(validate_img / 255)
    #     validate_code = self._decode(pre)
    #     print("successful get code")
    #     self.validate_code = validate_code
    #     print("validate code is {}".format(self.validate_code))
    #     return validate_code

    def _decode(self, y):
        y = np.argmax(np.array(y), axis=2)[:, 0]
        return "".join([str(x) for x in y])

    def _save_cookies(self, cookies=None):
        if cookies is None:
            cookies = self.cookies
        with open("./cookies.json", "w") as f:
            json.dump(cookies, f)

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
                "http://ecardfw.upc.edu.cn:20086/Login/LoginBySnoQuery",
                data=post_data,
                cookies=self.cookies,
                headers=self.headers,
            )
        except Exception as e:
            logger.info("error when login, msg{}".format(e))
            raise
        # resp_json = json.loads(login_resp.content)
        resp_json = login_resp.json()
        if not resp_json["IsSucceed"]:
            raise Exception("login failed", "captcha_error")
        # update cookies
        self.cookies["hallticket"] = login_resp.cookies["hallticket"]
        self.cookies["username"] = login_resp.cookies["username"]
        # save cookire
        self._save_cookies()

        return self.cookies

    def get_cookies(self, retry=None):
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
                if e.args[1] == "captcha_error":
                    logger.warning("captcha error")
                # raise
                count += 1
            else:
                break
        else:
            logger.error("Hit maximum try")
            raise Exception('Maximum try!')
        self.redis.hmset(self.no, {"hallticket": self.cookies["hallticket"]})
        logger.debug("Store user {} hallticket in redis".format(self.no))
        return self.cookies

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

    def test(self):
        img = self._get_validate_img()
        code = self._get_validate_code_ocr(img)
        logger.info("Validation code is {}".format(code))
        cv2.imshow("Test image", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def show_img(self, img):
        cv2.imshow("Test image", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def test():
    username = os.getenv("CARDNO")
    password = os.getenv("PASSWORD")
    logger.info("CardNo is {}, password is {}".format(username, password))
    test_login = Login(card_no=username, password=password, retry=15)
    cookies = test_login.get_cookies()
    print(cookies)
    # test_login.test()


if __name__ == "__main__":
    test()
