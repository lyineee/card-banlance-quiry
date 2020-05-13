import requests as rq 
import json 
import time

class CardBanlanceQuiry(object):

    banlance_url='http://ecardfw.upc.edu.cn:20086/User/GetCardInfoByAccountNoParm'
    history_url='http://ecardfw.upc.edu.cn:20086/Report/GetMyBill'
    account='95044'
    today=None
    banlance=None

    def __init__(self,cookies_path='./cookies.json'):
        # get cookies
        with open(cookies_path,'r') as f:
            self.cookies=json.load(f)
        # get date
        self.today=time.strftime("%Y-%m-%d", time.localtime())
    
    def quiry_banlance(self):
        try:
            res=rq.post(self.banlance_url,cookies=self.cookies,data={'json':'ture'})
            quiry_json=json.loads(res.json()['Msg'])
            self.banlance=int(quiry_json['query_card']['card'][0]['db_balance'])/100
        except Exception as e:
            print('quiry banlance error')
            print(e)
            raise
        return self.banlance

    def quiry_today(self):
        try:
            res=rq.post(self.history_url,cookies=self.cookies,data={'sdate':self.today,'edate':self.today,'account':self.account})
            self.today=0
            for i in res.json()['rows']:
                val=i['TRANAMT']
                if val < 0:
                    self.today+=val
        except Exception as e:
            print('quiry history error')
            print(e)
            raise
        return self.today

if __name__ == "__main__":
    test=CardBanlanceQuiry()
    print(test.quiry_banlance())
    print(test.quiry_today())
    input()
        
        
