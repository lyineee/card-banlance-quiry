import base64
import json
import os
import time

import cv2
import numpy as np
import requests as rq
import tensorflow as tf


class Login(object):

    headers = {
        'Host': 'ecardfw.upc.edu.cn:20086',
        'Proxy-Connection': 'keep-alive',
        'Content-Length': '72',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'http://ecardfw.upc.edu.cn:20086',
        'Referer': 'http://ecardfw.upc.edu.cn:20086/',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9,zh-TW;q=0.8,en-US;q=0.7,en;q=0.6,fi;q=0.5',
    }

    def __init__(self, card_no, password, retry=5):
        self.no = card_no
        self.pwd = password
        self.pwd_base64 = base64.b64encode(
            password.encode('utf-8')).decode('ascii')
        self.retry = retry
        self.cookies = {}
        self.validate_code = None

        self.input_width = 109
        self.input_height = 41

        # load keras model
        print('start loading keras model...')
        try:
            self.model = tf.keras.models.load_model('./result.h5')
        except Exception as e:
            # raise Exception('error when load model')
            print('error when load model')
            raise
        print('successfully load keras model')

    def _get_cookies(self):
        try:
            resp = rq.get('http://ecardfw.upc.edu.cn:20086/')
            self.cookies = {
                'ASP.NET_SessionId': resp.cookies['ASP.NET_SessionId']}
        except Exception as e:
            # raise Exception('error when get cookie')
            print('error when get cookie')
            raise

    def _get_validate_img(self):
        print('start get captcha image')
        validate_code_time = str(time.time()).replace('.', '')
        validate_code_url = 'http://ecardfw.upc.edu.cn:20086/Login/GetValidateCode?time={}'.format(
            validate_code_time)
        validate_code_resp = rq.get(validate_code_url, cookies=self.cookies)
        if validate_code_resp.status_code == 200:
            with open('./validate_code_tmp.jpg', 'wb') as f:
                f.write(validate_code_resp.content)
                f.flush()
                validate_img = cv2.imread(f.name)
            os.remove('./validate_code_tmp.jpg')
        else:
            raise Exception('error when get validate image')
        print('successfully get captcha image')
        return validate_img

    def _get_validate_code(self, validate_img):
        validate_img = cv2.resize(validate_img, (self.input_width, self.input_height)).reshape(
            (1, self.input_height, self.input_width, 3))
        print('start get code')
        pre = self.model.predict(validate_img/255)
        validate_code = self._decode(pre)
        print('successful get code')
        self.validate_code = validate_code
        print('validate code is {}'.format(self.validate_code))
        return validate_code

    def _decode(self, y):
        y = np.argmax(np.array(y), axis=2)[:, 0]
        return ''.join([str(x) for x in y])

    def _save_cookies(self, cookies=None):
        if cookies is None:
            cookies = self.cookies
        with open('./cookies.json', 'w') as f:
            json.dump(cookies,f)

    def _login(self):
        assert(self.validate_code is not None)
        post_data = {'sno': self.no, 'pwd': self.pwd_base64,
                     'ValiCode': self.validate_code, 'remember': '1', 'uclass': '1', 'json': 'true'}
        try:
            login_resp = rq.post('http://ecardfw.upc.edu.cn:20086/Login/LoginBySnoQuery',
                                 data=post_data, cookies=self.cookies, headers=self.headers)
        except Exception as e:
            print('error when login')
            raise
        resp_json = json.loads(login_resp.content)
        if not resp_json['IsSucceed']:
            raise Exception('login failed', 'captcha_error')
        # update cookies
        self.cookies['hallticket'] = login_resp.cookies['hallticket']
        self.cookies['username'] = login_resp.cookies['username']
        # save cookire
        self._save_cookies()

        return self.cookies

    def get_cookies(self):
        retry = 0
        while retry <= self.retry:
            self._get_cookies()
            val_img = self._get_validate_img()
            self._get_validate_code(val_img)
            try:
                self._login()
            except Exception as e:
                if e.args[1] == 'captcha_error':
                    print('captcha error')
                # raise
                retry += 1
            else:
                break
        else:
            print('try too many times')
            return 0
        return self.cookies


def test():
    username='your_user_name'
    password='your_pass_word'
    test_login = Login(card_no=username,password=password,retry=7)
    cookies = test_login.get_cookies()
    print(cookies)


if __name__ == "__main__":
    test()
