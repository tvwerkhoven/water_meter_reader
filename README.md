# Analog water meter reading with line sensor on Raspberry Pi

## Hardware

- Water meter (any model with a rotating disk with different infrared reflection should do). I have a Sensus 520/620 meter
- Raspberry Pi with pre-soldered GPIO pins (any RPi will do, I tested on RPi0W and RPi3B+)
- Line sensor (at least with digital out, prefereably also analog out to ease debugging. Working on 3.3V or 5.0V, I used https://www.hackerstore.nl/Artikel/26)
- Jumper cables to connect to RPi (easier than soldering)
- Arduino or oscilloscope (optional but recommended to ease electronic debugging)
- Some metal/wood/putty/screws for sensor mounting

## Install

### Arduinoscope 

If you have an arduino: get arduinoscope working http://www.instructables.com/id/Another-Arduino-Oscilloscope/

### Debug with oscilloscope

Connect line sensor to oscilloscope, then try to find the best orientation to detect the contrast in reflection. For me this was under a ±45 degree angle with the plastic window of the water meter, I got a contrast of ±0.5V to ±2.5V.

### Calibration

Once you are comfortable you know how the sensor works, mount it. Optionally use the potentiometer to adjust the digital out threshold. This should ideally be in the midpoint of the min and max voltage. For me this was at ±1.5V ((2.5+5)/2).

## Software

### Pre-requisites

Install python3-gpiozero

### Test libraries

Run ./read_ldr.py

### Set up domoticz

1. Create dummy hardware, note idx
2. Create virtual water sensor, using JSON
   1. `curl --insecure "https://127.0.0.1:10443/json.htm?type=createvirtualsensor&idx=<dummy hardware idx>&sensorname=Water&sensortype=113"`
   2. `curl --insecure "https://127.0.0.1:10443/json.htm?type=setused&idx=<idx of sensor just created>&name=RFXMeter&switchtype=2&used=true"`
3. Edit name of virtual sensor via web interface, set current value
4. Update RFX division to 1000 for water in Domoticz setting (if you're updating per liter)
5. Test updating
   1. `curl --insecure "https://127.0.0.1:10443/json.htm?type=command&param=udevice&idx=<sensor idx>&svalue=1"`
6. Enter domoticz details in script preamble

### Set up influxdb

1. Create database (e.g. 'smarthome')
2. Enter influxdb details in script preamble
3. Set current value explicitly in influxdb, the rest will be added
   1. Call `curl -i -XPOST http://localhost:8086/write?db=smarthometest --data-binary "water,type=potable,device=sensus value=653623"`

### Install worker

Install water_worker.py somewhere

Add 

    @reboot /home/pi/meter_water/water_worker.py

to crontab

## Reference

- https://www.domoticz.com/forum/viewtopic.php?f=28&t=17123&p=139918&hilit=water+meter#p139918
- https://www.raspberrypi.org/documentation/usage/gpio/
- https://www.domoticz.com/wiki/Python_-_Read-out_of_DDS238_kWh-meter_and_upload_to_Domoticz_and_to_PVOutput#Creating_the_Shell_script_used_in_cron
- https://gpiozero.readthedocs.io/en/stable/api_input.html#line-sensor-trct5000
- http://www.instructables.com/id/Another-Arduino-Oscilloscope/
- https://gathering.tweakers.net/forum/list_messages/1653735 
- https://www.circuitsonline.net/forum/view/message/1484447#1484447
- https://gathering.tweakers.net/forum/list_messages/1595957
- https://www.circuitlab.com/circuit/eae95u/raspberry-pi-kwh-meter/
- https://hackerstore.nl/Artikel/26
