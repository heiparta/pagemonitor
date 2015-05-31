FROM ubuntu:trusty
MAINTAINER Heikki Partanen <heikki.partanen@gmail.com>

WORKDIR /app

RUN apt-get update && apt-get install -y python-pip python-dev

ADD ./requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

ADD . /app

VOLUME ["/etc/pagemonitor/pagemonitor.json"]
VOLUME ["/var/log/"]

CMD ["python", "/app/src/pagemonitor.py"]
