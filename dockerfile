FROM python:3

WORKDIR /usr/src/app

ENV TIME_ZONE=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TIME_ZONE /etc/localtime && echo $TIME_ZONE > /etc/timezone

COPY ["requirements.txt", "./"]
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY ["main.py", "student_card.py", "./"]

CMD [ "python", "./main.py" ]