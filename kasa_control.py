#!/usr/bin/python
# Copyright (C) 2016 by Adrian Reber
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Based on
# https://georgovassilis.blogspot.de/2016/05/controlling-tp-link-hs100-wi-fi-smart.html

# This script communicates with the TP-LINK WI-FI SMART PLUG, HS-100.
# It is based on the work from the link above. Instead of shell script
# it is now all implemented in python and the commands are encoded and
# decoded in the script.

# The initial set up of the device still needs the app from TP-LINK, but
# once it has been integrated in the local WLAN this script can be used
# to control the device.

# The protocol used is JSON which is XOR'd and then transmitted to the device.
# Same goes for the answers. The JSON string is XOR'd with the previous
# character of the JSON string and the value of the first XOR operation
# is 0xAB.  Additionally each message is prefixed with '\x00\x00\x00\x23'.

# Firmware analyzed with the help of binwalk like described here:
# http://blog.ioactive.com/2016/03/got-15-minutes-to-kill-why-not-root.html
# Based on US firmware donwloaded from:
# http://www.tp-link.us/res/down/soft/HS100(US)_V1_151016.zip


# Running strings on /usr/bin/shd of the extracted firmware gives
# following possible commands:
# system                # verified
# reset
# get_sysinfo           # verified
# set_test_mode
# set_dev_alias         # verified
# set_relay_state       # verified
# check_new_config
# download_firmware
# get_download_state
# flash_firmware
# set_mac_addr
# set_device_id
# set_hw_id
# test_check_uboot      # verified; no idea what output means
# get_dev_icon
# set_dev_icon
# set_led_off           # verified
# set_dev_location

# Running strings on /usr/bin/shdTester reveals a few additional commands,
# probably only for HS110
# vtarget
# itarget
# start_calibration
# emeter
# vgain
# igain
# set_vgain_igain
# get_vgain_igain
# get_realtime
# start_emeter_cal
# get_emeter_realtime

# modified by curesec gmbh, we added some commands, everything else, like the header obove, remains unchanged.


import socket
import json
import argparse
import sys

# default port is 9999
port = 9999

command = {}
info = False

# Each message send to the device is prefixed with this sequence.
prefix = '\x00\x00\x00\x23'
key = 0xab
code = 0


def decode(a):
    code = key
    b = ""
    for i in a:
        b += chr(ord(i) ^ code)
        code = ord(i)

    return b


def encode(a):
    code = key
    b = ''
    for i in a:
        b += chr((ord(i) ^ code))
        code = (ord(b[len(b) - 1]))
    return b

def reset_cmd():
	#reset plug with delay in seconds, added by curesec
    command["system"] = {"reset": {"delay":1}}

def reboot_cmd():
    #reboot device with delay in seconds, added by curesec
    command["system"] = {"reboot":{"delay":1}}

def unbind_cmd():
    #unbind plug from any account, added by curesec
    unbind = {"unbind":None}
    command["cnCloud"] = unbind

def bind_cmd():
    #bind plug to your account if not already added to another one, if so use unbind first, added by curesec
    bind = {"bind":{"username":"yourUsername", "password":"yourPassword"}}
    command["cnCloud"] = bind
    return False

def emeter_cmd():
    #current energy consumption, added by curesec
    command["emeter"] = {"get_realtime":null}

def on_cmd():
    relay_state = {"set_relay_state": {"state": 1}}
    command["system"] = relay_state
    return False


def off_cmd():
    relay_state = {"set_relay_state": {"state": 0}}
    command["system"] = relay_state
    return False

def led_on_cmd():
    led = {"set_led_off": {"off": 0}}
    command["system"] = led
    return False


def led_off_cmd():
    led = {"set_led_off": {"off": 1}}
    command["system"] = led
    return False


def alias_cmd():
	#device name
    alias = {"set_dev_alias": {"alias": args.alias}}
    command["system"] = alias
    return False


def info_cmd():
    global info
    info = True
    command["system"] = {"get_sysinfo": None}
    return False


def state_cmd():
    command["system"] = {"get_sysinfo": None}
    return True


description="Control TP-LINK HS100/HS110 WiFi Smart Plug"
parser = argparse.ArgumentParser(description=description)
parser.add_argument('-d', '--debug', help="Print additional debug output",
                    action="store_true")
parser.add_argument('-H', '--host', required=True, action="store",
                    help="Address of the smart plug")
parser.add_argument('-a', '--alias', action="store", default="hs110",
                    help="Device Alias")
parser.add_argument(
    "command",
    help="Command to execute",
    choices=[
        'on',
        'off',
        'led_on',
        'led_off',
        'alias',
        'state',
        'info',
	    'bind',
        'unbind',
        'reset',
        'reboot',
        'emeter'])
args = parser.parse_args()

func = getattr(__import__('__main__'), args.command + "_cmd", None)
state = func()


result = json.dumps(command, indent=1)
if args.debug:
    print ("DEBUG: About to send:\n%s\n" % result)

send = prefix
send += encode(result)

sock = socket.socket()
sock.connect((args.host, port))

sock.send(send)

result = sock.recv(8096)
parsed = json.loads(decode(result[4:]))

if args.debug:
    print ("DEBUG: Got following answer:")
if args.debug or info:
    print("%s\n" % json.dumps(parsed, indent=1))

if state:
    if parsed["system"]["get_sysinfo"]["relay_state"] == 1:
        print("Power ON")
        code = 1
    else:
        print("Power OFF")
        code = 2

sys.exit(code)