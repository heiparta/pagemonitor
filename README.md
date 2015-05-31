pagemonitor
===========

Lightweight script to monitor URLs and get email notification if they are down

Installation
============
* Set up and activate new Python 2.7 virtualenv
* Clone the repo
* Install dependencies: pip install -r requirements.txt
* Create configuration file pagemonitor.json (see example.json)
* Run the script: python src/pagemonitor.py
* After checking that it works as expected, set it up to be started with something like supervisor or init

Running with docker
===================
* docker pull heiparta/pagemonitor
* Create configuration file conf.json
* docker run -d -v <absolute path to conf.json>:/etc/pagemonitor/pagemonitor.json heiparta/pagemonitor
