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
# Known issues:
# 1. Make sure you set the RFX division for water meter to 1000 (not 100, 
#	the default), otherwise Domoticz will only report 1 m^3/100 = 10 liter 
#   updates instead of 1 m^3/1000 = 1 liter
#
# Known risks:
# 1. The sensor might falsely trigger when the rotating disk ends exactly in 
#   the middle of the edge between high and low contrast, causing the sensor
#   to give a voltage exactly around the threshold voltage. This is 
#   partially mitigated by having a minimum delay time, but this does not
#   solve it. Problem does not seem very severe


# Domoticz settings
domoticz_water_idx = 23 		# IDX for virtual water sensor
domoticz_ip = "127.0.0.1"		# IP of domoticz server (127.0.0.1 for localhost = same computer)
domoticz_protocol = "https"		# Protocol to use (http or https)
domoticz_port = 10443			# Webserver port of domoticz (either http or https)

influxdb_ip = "127.0.0.1"		# IP of influxdb server (127.0.0.1 for localhost = same computer)
influxdb_protocol = "http"		# Protocol to use for influxdb (http or https)
influxdb_port = 8086			# port
influxdb_db = "smarthome"		# database to use
influxdb_query = "waterv2 sensus=" # prefix of query, will be appended with ' value =1'

meter_logf = None #'/tmp/water_worker.log' # log file, or None for no logging to disk
meter_delay = 0.1				# Minimum delay between counts in seconds 
								# (low-pass filter for potential sensor 
								# noise)
meter_lastupdate = 0		   	# Time at which meter was last updated (seconds since epoch)
meter_count_l = None			# Initial meter in liter - will be updated 
								# with meter reading if it exists in domoticz
meter_offset_l = 0				# Meter offset (if used)
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

def domoticz_update(count):
	# Todo: make value formatting dynamic based on meter settings
	req_url = "{}://{}:{}/json.htm?type=command&param=udevice&idx={}&svalue={}".format(domoticz_protocol, domoticz_ip, domoticz_port, domoticz_water_idx, count)
	# Set timeout, otherwise it will hang forever
	try:
		httpresponse = requests.get(req_url, verify=False, timeout=5)
	except requests.exceptions.Timeout as inst:
		logging.warn("Could not update meter reading in domoticz due to timeout: {}, failing".format(inst))
		raise

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
	except requests.exceptions.Timeout as inst:
		logging.warn("Could not update meter reading in influxdb due to timeout: {}, failing".format(inst))
		raise

# These functions will be called when there is a line / no line detected.
# N.B. That 'line' or 'no line' means low or high reflection here.
def call1():
	global meter_count_l, meter_lastupdate
	now = time.time()
	logging.debug("Line detected - {}".format(meter_sensor._queue.queue))
	if (now - meter_lastupdate) < meter_delay:
		logging.debug("Skipping, update too fast since last")
		return

	try:
		influxdb_update(0.5, influxdb_protocol, influxdb_ip, influxdb_port, influxdb_db, influxdb_query)
	except:
		logging.warn("Failed to update influxdb")

	meter_count_l = meter_count_l + 1
	try:
		domoticz_update(meter_count_l)
	except:
		logging.warn("Failed to update domoticz")

	logging.info("Updated water meter to {}".format(meter_count_l))
	meter_lastupdate = now

def call2():
	logging.debug("No line detected - {}".format(meter_sensor._queue.queue))
	try:
		influxdb_update(0.5, influxdb_protocol, influxdb_ip, influxdb_port, influxdb_db, influxdb_query)
	except:
		logging.warn("Failed to update influxdb")

def domoticz_init(ip, port, meter_idx, prot="http"):
	# Get current water meter reading from domoticz, return meter_count_l

	logging.info("Get current water meter reading from domoticz")
	
	# E.g. https://127.0.0.1:10443/json.htm?type=devices&rid=
	req_url = "{}://{}:{}/json.htm?type=devices&rid={}".format(prot, ip, port, meter_idx)

	# Try a few times in case domoticz has not started yet. We give domoticz 
	# 10*10 seconds (±2 minutes) to start
	for i in range(10):
		try:
			resp = requests.get(req_url, verify=False, timeout=5)
			break
		except:
			logging.warn("Could not get current meter reading. Will retry in 10sec. ({}/{})".format(i, 10))
			time.sleep(10)
			if (i == 9):
				logging.warn("Could not get current meter reading. Failing.")
				raise

	# Get meter offset, given as float
	meter_offset_str = resp.json()['result'][0]['AddjValue'] # like '13.456'
	meter_offset_l = int(float(meter_offset_str)*1000)

	# This tries to get the meter reading from JSON. Assumes RFX type of 
	# format
	meter_count_str = resp.json()['result'][0]['Counter'] # like '13.456 m3'
	meter_count_l = int(float(meter_count_str[0:meter_count_str.index(" ")])*1000) - meter_offset_l

	logging.debug("Using {} liter as current reading (counter={}, offset={})...".format(meter_count_l, meter_count_str, meter_offset_l))
	return meter_count_l

meter_count_l = domoticz_init(domoticz_ip, domoticz_port, domoticz_water_idx, domoticz_protocol)

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
