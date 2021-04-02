from typing import Union
import requests as rq
import time
import json
import redis

# r = redis.Redis()
# r = redis.StrictRedis()
code_set_name = "classroom_code"


def get_all_class_room(redis: redis.Redis):
    resp = rq.get("https://app.upc.edu.cn/freeclass/wap/default/search-all")
    try:
        data = resp.json()
        if data["e"] != 0:
            raise Exception(data["m"])
        # return data["all"]
        for _, class_list in data["d"]["all"].items():
            for classroom in class_list:
                redis.sadd(code_set_name, classroom["code"])
    except json.JSONDecodeError as e:
        raise Exception(e.msg)


def get_free_classroom(class_no: Union[int, str], redis: redis.Redis):
    url = "https://app.upc.edu.cn/freeclass/wap/default/search-all"
    date = time.strftime("%Y-%m-%d")
    payload = {"xq": "青岛校区", "date": date, "lh": "全部", "jc[]": str(class_no)}
    resp = rq.post(url, data=payload)
    try:
        data = resp.json()
        if data["e"] != 0:
            raise Exception(data["m"])
        for building_name, classroom_list in data["d"]["js"].items():
            for classroom in classroom_list:
                redis.sadd(classroom["code"], int(class_no))
    except json.JSONDecodeError as e:
        raise Exception(e.msg)


def clear_all(redis: redis.Redis):
    class_set = redis.smembers(code_set_name)
    for item in class_set:
        name = item.decode()
        redis.delete(name)
    redis.delete("class")


def decide_class_now(time_now=None) -> int:
    time_seq = [
        "08:00",
        "08:50",
        "09:50",
        "10:55",
        "11:40",
        #
        "14:00",
        "14:50",
        "15:55",
        "16:45",
        #
        "19:00",
        "19:50",
        "20:40",
        "21:30",
    ]
    time_now = time_now if time_now else time.strftime("%H:%M")
    for index, t in enumerate(time_seq):
        if time_now < t:
            return index + 1
    return 13


def get_classify_data(redis: redis.Redis) -> dict:
    class_list = []
    row = redis.smembers(code_set_name)
    for item in row:
        class_list.append(item.decode())
    # classification
    data = {"dh3": [], "dh2": [], "nt2": [], "nt3": [], "nt4": []}
    for code in class_list:
        if code[:3] == "DH3":
            data["dh3"].append(code)
        elif code[:3] == "DH2":
            data["dh2"].append(code)
        elif code[:3] == "NT2":
            data["nt2"].append(code)
        elif code[:3] == "NT3":
            data["nt3"].append(code)
        elif code[:3] == "NT4":
            data["nt4"].append(code)
    # sort
    for k, v in data.items():
        data[k] = sorted(v, key=lambda key: int(key[2:]))
    return data


def get_free_count(classroom_code) -> int:
    free_set = r.smembers(classroom_code)
    free_count = 0
    for i in range(decide_class_now(), 14):
        if str(i).encode() in free_set:
            free_count += 1
        else:
            break
    return free_count


def update_class(db: redis.Redis):
    clear_all(db)
    get_all_class_room(db)
    for i in range(1, 14):
        get_free_classroom(i, db)


if __name__ == "__main__":
    # data = dict()
    # for location, codes in get_classify_data(r).items():
    #     free_list = []
    #     for code in codes:
    #         free_list.append(get_free_count(code))
    #     data[location] = free_list
    # print(data)
    # update_class(r)
    pass
