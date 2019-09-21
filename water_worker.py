#!/usr/bin/env python3
# 
# Water meter reader. Max update rate of domoticz over JSON is ±1Hz, or 60 
# liter per minute (1 update per revolution), sufficient for our purposes. 
# My tap runs at 7.5 liter/minute
#
# Todo:
# 1. Check what happens if updates are faster than json calls (do these 
#    queue or not?) --> JSON calls are quite fast (<<second), probably not a problem
# 2. Add scheduler that does a NOOP every hour if there is no new data (to 
#    fill the graph) - https://stackoverflow.com/questions/23512970/how-to-implement-multiple-signals-in-a-program
#
#
# Known risks:
# 1. The sensor might falsely trigger when the rotating disk ends exactly in 
#   the middle of the edge between high and low contrast, causing the sensor
#   to give a voltage exactly around the threshold voltage. This is 
#   partially mitigated by having a minimum delay time, but this does not
#   solve it. Problem does not seem very severe


influxdb_ip = "127.0.0.1"		# IP of influxdb server (127.0.0.1 for localhost = same computer)
influxdb_protocol = "http"		# Protocol to use for influxdb (http or https)
influxdb_port = 8086			# port
influxdb_db = "smarthomev3"		# database to use
influxdb_query = "waterv3,quantity=potable,source=sensus value=" # prefix of query, will be appended with value

meter_logf = None #'/tmp/water_worker.log' # log file, or None for no logging to disk
meter_delay = 0.01				# Minimum delay between counts in seconds 
								# (low-pass filter for potential sensor 
								# noise). 0.01 is ~50l/s
meter_lastupdate = 0		   	# Time at which meter was last updated (seconds since epoch)
meter_sensor = None 			# Init global sensor

import logging
logging.basicConfig(filename=meter_logf, level=logging.DEBUG, format='%(asctime)s %(message)s')
logging.debug("Starting script, loading libs...")

# Open libraries
import time
import os
from gpiozero import LineSensor
from signal import pause
import requests

def influxdb_update(increment, prot='http', ip='127.0.0.1', port='8086', db="smarthometest", query="water,type=usage,device=sensus"):
	"""
	Push value 'increment' to influxdb with second precision, which should 
	have the value of the amount of water used (e.g. 1 for 1 liter)
	"""

	# Something like req_url = "http://localhost:8086/write?db=smarthometest&precision=s"
	req_url = "{}://{}:{}/write?db={}&precision=s".format(prot, ip, port, db)
	# Something like post_data = "water,type=usage,device=sensus value=1"
	post_data = "{}{:f}".format(query,increment)
	try:
		httpresponse = requests.post(req_url, data=post_data, verify=False, timeout=5)
	except Exception as inst:
		logging.warn("Could not update meter reading in influxdb: {}, failing".format(inst))

# These functions will be called when there is a line / no line detected.
# N.B. That 'line' or 'no line' means low or high reflection here.
def update():
	global meter_lastupdate
	now = time.time()
	if (now - meter_lastupdate) < meter_delay:
		logging.debug("Skipping, update too fast since last")
		return
	try:
		influxdb_update(0.5, influxdb_protocol, influxdb_ip, influxdb_port, influxdb_db, influxdb_query)
	except:
		logging.warn("Failed to update influxdb")

	meter_lastupdate = now
	logging.info("Updated water meter")

def call1():
	logging.debug("Line detected - {}".format(meter_sensor._queue.queue))
	update()

def call2():
	logging.debug("No line detected - {}".format(meter_sensor._queue.queue))
	update()

# Initiate line sensor from GPIO. We use 20Hz and a queue length of 5, such 
# that we have an effective sample rate of 5 Hz (supersampled 5x). Default 
# is 100 Hz but this takes more CPU than needed for this slow meter
logging.debug("Initiating linesensor, queue_len 10, sample @ 40Hz")
meter_sensor = LineSensor(4, queue_len=10, sample_rate=40)

meter_sensor.when_line = call1
meter_sensor.when_no_line = call2

# Start waiting loop
logging.info("Starting waiting loop forever")
pause()
