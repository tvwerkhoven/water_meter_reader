#!/usr/bin/env python3
# Test script for debugging gpio interface on e.g. raspberry pir

print('starting script')
import time
from gpiozero import LineSensor
from signal import pause

import gpiozero
print('making sensor')
#pir = MotionSensor(4)
sensor = LineSensor(4)

def call1():
	print("Line detected @ {}".format(time.time()))


def call2():
	print("No line detected @ {}".format(time.time()))


print('registering callbacks')
sensor.when_line = call1
sensor.when_no_line = call2

print('starting handler')
pause()

