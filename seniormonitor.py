#!/opt/bin/python
import sys
import configparser

import logging
import datetime
import RPi.GPIO as GPIO
from gpiozero import MotionSensor
import time
import os
from twilio.rest import Client

#SlotRecord is used to track information of events happening
#in a given slot
class SlotRecord:
# __init__, the constructor, takes as argument beginDateTime, endDateTime, and index
# The slot has attributes begineDateTime, endDateTime, motionDetectedCounter
#  and index
    def __init__(self, beginDateTimeObj, endDateTimeObj, index):
        self.beginDateTimeObj = beginDateTimeObj
        self.endDateTimeObj = endDateTimeObj
        self.motionDetectedCounter = 0
        self.index = index
    def print(self):
        logging.info("sr index {} beginDateTimeObj {} endDateTimeObj {} motionDetectedCounter {} "\
                     .format(self.index, self.beginDateTimeObj,  self.endDateTimeObj,\
                                             self.motionDetectedCounter))

# prepareMonitorArrayFromConfigInfo takes as input the configParser object and isDemo flag.
# This function prepares the monitor array.
# Monitor array has slots for the monitored time period.
# Monitor time perioed is obtained from the configParser object
# ConfigParser object has read it from the configuration file

def prepareMonitorArrayFromConfigInfo(config, isDemo):
    logging.info("prepareMonitorArrayFromConfigInfo isDemo {}".format(isDemo))

    slotRecordArray = []

    today = datetime.datetime.today().strftime('%Y%m%d')

    logging.info("today {} {}".format(today, datetime.datetime.today().strftime("%H%M%S")))

    monitorStartHour=config['DEFAULT']['MonitorStartHour']
    monitorEndHour=config['DEFAULT']['MonitorEndHour']
    slotDuration=config['DEFAULT']['SlotDuration']

    beginDateTimeStr = today + monitorStartHour
    beginDateTimeObj = datetime.datetime.strptime(beginDateTimeStr, "%Y%m%d%H%M")

    endDateTimeStr = today + monitorEndHour
    endDateTimeObj = datetime.datetime.strptime(endDateTimeStr, "%Y%m%d%H%M")
    logging.info("beginDateTimeObj {} endDateTimeObj  {} slotDuration {} "\
                 .format(beginDateTimeObj ,endDateTimeObj, slotDuration))
    if(isDemo):
        logging.info("Demo mode. Overriding monitoring window for demo")
        now = datetime.datetime.now()
        demoBeginTime = now + datetime.timedelta(seconds=5)
        demoEndTime = now + datetime.timedelta(seconds=25)
        logging.info("demoBeginTime {}  demoEndTime {} ".format(demoBeginTime, demoEndTime))
        beginDateTimeObj = demoBeginTime.replace(microsecond=0)
        endDateTimeObj = demoEndTime.replace(microsecond=0)
        slotDuration = 5
        logging.info("beginDateTimeObj {} endDateTimeObj {} slotDuration {}"\
                     .format(beginDateTimeObj, endDateTimeObj, slotDuration))


    index = 0
    tempDateTimeObj = beginDateTimeObj
    while(tempDateTimeObj < endDateTimeObj):
        #Creating individual slots in the given interval
        slotDateTimeBegin = tempDateTimeObj
        tempDateTimeObj = tempDateTimeObj + datetime.timedelta(seconds=int(slotDuration))
        slotDateTimeEnd = tempDateTimeObj
        slotRecord = SlotRecord(slotDateTimeBegin, slotDateTimeEnd, index)
        logging.info("slotRecord {} {} {} {} ".format(\
                                                        slotRecord.index, \
                                                        slotRecord.beginDateTimeObj, \
                                                        slotRecord.endDateTimeObj, \
                                                        slotRecord.motionDetectedCounter))
        slotRecordArray.append(slotRecord)
        index += 1

    logging.info("leaving prepareMonitorArrayFromConfigInfo ")

    return slotRecordArray


def getTwilioClient(config):
    logging.info("getTwilioClient")
    twilioAccountSid = config['DEFAULT']['TwilioAccountSid']
    twilioAuthCode = config['DEFAULT']['TwilioAuthCode']
    logging.info("twilioAccountSid -{}-, twilioAuthCode --{}-"\
                 .format(twilioAccountSid, twilioAuthCode))
# Client is a Class from twilio library. This helps make calls
# using Twilio APIs
    twilioClient = Client(twilioAccountSid, twilioAuthCode)
    return twilioClient

def makeAlarmCall(twilioClient, config):
    logging.info("makeAlarmCall")
    alarmMessage = config['DEFAULT']['AlarmMessage']
    callerPhoneNumber =  config['DEFAULT']['CallerPhoneNumber']
    receiverPhoneNumber = config['DEFAULT']['ReceiverPhoneNumber']    
# Twi ml Twilio markup language    
    twimlMessage = "<Response><Say> " + alarmMessage + "</Say> </Response>"
    logging.info("alarmMessage -{}- , receiverPhoneNumber -{}- , callerPhoneNumber -{}- "\
                 " twimlMessage -{}- "\
                 .format(alarmMessage, callerPhoneNumber, receiverPhoneNumber, twimlMessage))
    try:
        call = twilioClient.calls.create(
            twiml=twimlMessage,
            to=receiverPhoneNumber,
            from_=callerPhoneNumber,
        )
        logging.info(" call response {} ".format(call.sid))
        logging.info(" returning from makeAlarmCall ")
    except Exception as e:
        logging.info("makeAlarmCall an unexpected error occurred {}".format(e))


def printSlotRecordArray(slotRecordArray):
    logging.info("printSlotRecordArray ")
    for slotRecord in slotRecordArray:
        slotRecord.print()


def checkForMotionDetection(slotRecordArray):
    logging.info("checkForMotionDetection  ")
    idx = 0
    for sR in slotRecordArray:
        logging.info("Slot idx {} index {} beginDateTimeObj {} endDateTimeObj {} motionDetectedCounter {} "\
                     .format(idx, sR.index, sR.beginDateTimeObj,  sR.endDateTimeObj,\
                                             sR.motionDetectedCounter))
        if sR.motionDetectedCounter > 0:
            logging.info("MotionDetecded. Returning True")
            return True
        idx +=1
    logging.info("No  MotionDetecded. Returning False")
    return False



# if currentDateTimeObj is before than slot window start, returns -1
# if currentDateTimeObj falls in existing slot returns index of the slot
# if currentDateTimeObj falls beyond the last slot, return -2
def findCurrentTimeSlotIndex(slotRecordArray, currentDateTimeObj):
    logging.info("in findCurrentTimeSlotIndex currentDateTimeObj  {}".format(currentDateTimeObj))
    idx = 0
    for sR in slotRecordArray:
        logging.info("sR.beginDateTimeObj {} sR.endDateTimeObj {} currentDateTimeObj {}"\
                     .format(sR.beginDateTimeObj, sR.endDateTimeObj, currentDateTimeObj))
        if(sR.beginDateTimeObj > currentDateTimeObj):
            logging.info("currentDateTimeObj is before the slot window start, returns -1")
            return -1
        if((sR.beginDateTimeObj < currentDateTimeObj)
           and (currentDateTimeObj <= sR.endDateTimeObj)):
            logging.info("Found the slot at idx {}  ".format(idx))
            return idx
        idx += 1
    logging.info("Could not find the slot in the array")
    return -2

def updateSlotRecordArray(slotRecordArray, currentDateTimeObj, slotIdx):
    logging.info("updateSlotRecordArray updating slot idx {} for time {} "\
                 "inital motionDetectedCounter {} " \
                 .format(slotIdx, currentDateTimeObj, \
                        slotRecordArray[slotIdx].motionDetectedCounter))
    slotRecordArray[slotIdx].motionDetectedCounter += 1
    logging.info("updateSlotRecordArray "\
                 "udpated motionDetectedCounter {} " \
                 .format(slotRecordArray[slotIdx].motionDetectedCounter))





#Configuration file is seniormonitor.config
#For demo, we can customize some of our parameters.
def main():
    isDemo = False
#If the application is being run in demo mode,
# set isDemo to True
    if len(sys.argv) == 2:
        if sys.argv[1] == "--demo":
            isDemo = True
            print ("Running in Demo mode")
    else:
        print("Not in Demo Mode")

    logging.basicConfig(filename='seniormonitor.log', \
                        format = '[%(lineno)d] %(message)s',\
                        level=logging.INFO)

    
    config = configparser.ConfigParser()
    config.read('seniormonitor.config')

    logging.info("Config parameters are MonitorStartHour {} "\
                 " MonitorEndHour {} SlotDuration {} "\
                 " LoopSleepTime {}  "\
                 " TwilioAccountSid -{}- TwilioAuthCode -{}- "\
                 .format(config['DEFAULT']['MonitorStartHour'],\
                         config['DEFAULT']['MonitorEndHour'],\
                         config['DEFAULT']['SlotDuration'],\
                         config['DEFAULT']['LoopSleepTime'],\
                         config['DEFAULT']['TwilioAccountSid'],\
                         config['DEFAULT']['TwilioAuthCode']))
    
    slotRecordArray = []
    slotRecordArray = prepareMonitorArrayFromConfigInfo(config, isDemo)
    logging.info("Printing the slotRecordArray from .prepareMonitorArrayFromConfigInfo")
    printSlotRecordArray(slotRecordArray)

    if isDemo == True:
        slotRecordArray = prepareMonitorArrayFromConfigInfo(config, isDemo)

    logging.info("==================================")
    logging.info("Printing the slotRecordArray.")
    printSlotRecordArray(slotRecordArray)

    LOOP_SLEEP = config['DEFAULT']['LoopSleepTime']
    if isDemo:
        LOOP_SLEEP = 4
# I am using logical GPIO pin 4        
    GPIO_PIN = 4

# We create an object of type MotionSensor
# This will read the input from PIR sensor
# at logical PIN 4
    pir = MotionSensor(GPIO_PIN)
    twilioClient = getTwilioClient(config)

    slotIdx = 0
    while True:
        logging.info("going to loop sleep \n")
        time.sleep(int(LOOP_SLEEP))
        logging.info("woken up from loop sleep \n")
        
        logging.info("=======================Iteration===============")
        currentDateTimeObj = datetime.datetime.today().replace(microsecond=0)
        logging.info("currentDateTime {} ".format(currentDateTimeObj))
        slotIdx = findCurrentTimeSlotIndex(slotRecordArray, currentDateTimeObj)

        if (slotIdx == -1):
            logging.info("currentDateTime {} falls before monitored window."\
                         .format(currentDateTimeObj))
            continue;
        if (slotIdx == -2):
            logging.info("currentDateTime {} falls outside monitored window."\
                         .format(currentDateTimeObj))
            break;
        logging.info("currentDateTime {} falls into monitored window."\
                     .format(currentDateTimeObj))

        if GPIO.input(GPIO_PIN) == GPIO.HIGH:
            logging.info("Motion detected will update slotIdx {}".format(slotIdx))
            updateSlotRecordArray(slotRecordArray, currentDateTimeObj, slotIdx)
        else:
            logging.info("GPIO_LOW will NOT update slotIdx.")


    isMotionDetected = checkForMotionDetection(slotRecordArray)
    logging.info("isMotionDetected {}".format(isMotionDetected))
        
    if isMotionDetected == False :
        makeAlarmCall(twilioClient, config)



if __name__ == "__main__":
    exit(main())








