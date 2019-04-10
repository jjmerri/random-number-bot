#!/usr/bin/env python3.6

# =============================================================================
# IMPORTS
# =============================================================================
import praw
import re
import time
import configparser
import logging
import os
import smtplib
import json
import requests
import uuid

from email.mime.text import MIMEText

# =============================================================================
# GLOBALS
# =============================================================================

VERSION = '1.1.5'

# Reads the config file
config = configparser.ConfigParser()
config.read("random_number_bot.cfg")

bot_username = config.get("Reddit", "username")
bot_password = config.get("Reddit", "password")
client_id = config.get("Reddit", "client_id")
client_secret = config.get("Reddit", "client_secret")

#Reddit info
reddit = praw.Reddit(client_id=client_id,
                     client_secret=client_secret,
                     password=bot_password,
                     user_agent='random_number_bot by /u/BoyAndHisBlob',
                     username=bot_username)

EMAIL_SERVER = config.get("Email", "server")
EMAIL_USERNAME = config.get("Email", "username")
EMAIL_PASSWORD = config.get("Email", "password")

DEV_EMAIL = config.get("RandomNumberBot", "dev_email")

RUNNING_FILE = "random_number_bot.running"
ENVIRONMENT = config.get("RandomNumberBot", "environment")
DEV_USER_NAME = config.get("RandomNumberBot", "dev_user")
RANDOM_ORG_API_KEY = config.get("RandomNumberBot", "random_org_api_key")
RANDOM_ORG_API_URL = 'https://api.random.org/json-rpc/2/invoke'
HTTP_TIMEOUT = 30.0

FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger('RandomNumberBot')
logger.setLevel(logging.INFO)

random_number_reply = """#{command_message} {random_numbers}
        
Paste the following values into their respective fields on the [random.org verify page](https://api.random.org/verify) to verify the winner.

**Random:**

{verification_random}

**Signature:**

{verification_signature}

---

[^(Give Feedback)](https://www.reddit.com/message/compose/?to=BoyAndHisBlob&subject=Feedback) ^| [^(Version {version} Source Code)](https://github.com/jjmerri/random-number-bot) ^| [^(Tip BoyAndHisBlob)](https://blobware-tips.firebaseapp.com)

^(This bot is maintained and hosted by BoyAndHisBlob.)"""

def send_dev_pm(subject, body):
    """
    Sends Reddit PM to DEV_USER_NAME
    :param subject: subject of PM
    :param body: body of PM
    """
    reddit.redditor(DEV_USER_NAME).message(subject, body)

def send_dev_email(subject, body, email_addresses):
    sent_from = DEV_EMAIL

    msg = MIMEText(body.encode('utf-8'), 'plain', 'UTF-8')
    msg['Subject'] = subject

    server = smtplib.SMTP_SSL(EMAIL_SERVER, 465)
    server.ehlo()
    server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
    server.sendmail(sent_from, email_addresses, msg.as_string())
    server.close()

def create_running_file():
    running_file = open(RUNNING_FILE, "w")
    running_file.write(str(os.getpid()))
    running_file.close()

def check_mentions():
    for mention in reddit.inbox.unread(limit=None):
        # Mark Read first in case there is an error we dont want to keep trying to process it
        mention.mark_read()
        process_mention(mention)

def process_mention(mention):
    logger.info(
        'Processing comment by {author} for {context}'.format(author=str(mention.author), context=mention.context))

    command_regex = r'^([ ]+)?/?u/{bot_username}[ ]+(?P<param_1>[\d]+)([ ]+(?P<param_2>[\d]+))?([ ]+)?$'.format(bot_username=bot_username)
    match = re.search(command_regex, mention.body, re.IGNORECASE)

    command_message = ''
    num_randoms = 0
    num_slots = 0

    if match and match.group("param_1") and match.group("param_2"):
        command_message = 'Your escrow spots:'
        num_randoms = int(match.group("param_1"))
        num_slots = int(match.group("param_2"))
        if(num_randoms > num_slots):
            num_randoms, num_slots = num_slots, num_randoms
    elif match and match.group("param_1"):
        command_message = 'The winner is:'
        num_randoms = 1
        num_slots = int(match.group("param_1"))
    else:
        #could be a normal mention not a command so just return
        return

    request = getRdoRequest(num_randoms, num_slots)

    responseData = {}
    try:
        response = requests.post(RANDOM_ORG_API_URL,
                      data=json.dumps(request),
                      headers={'content-type': 'application/json'},
                      timeout=HTTP_TIMEOUT)
        responseData = response.json()

        logger.info('API response for comment by {author} for {context} is {response}'
                    .format(author=str(mention.author), context=mention.context, response=str(responseData)))
    except Exception as err:
        logger.exception('Error calling RandomOrg API')

    if(responseData and 'result' in responseData):
        responseResult = responseData['result']
        mention.reply(random_number_reply.format(command_message = command_message,
                                   random_numbers = str(responseResult['random']['data']),
                                   verification_random = get_verification_random(responseResult['random']),
                                   verification_signature = str(responseResult['signature']),
                                   version = VERSION))
    else:
        logger.error('Error getting random nums {num_randoms} {num_slots}'.format(num_randoms=num_randoms, num_slots=num_slots))
        logger.error(str(responseData))
        try:
            if num_slots == 1:
                mention.reply('The number of slots must be greater than 1. Please fix the call and try again.')
            else:
                mention.reply('There was an error getting your random numbers from random.org. Please try again. '
                              'If you continue to experience issues or the bot becomes unresponsive please contact {DEV_USER_NAME}.'
                              .format(DEV_USER_NAME=DEV_USER_NAME))
                send_dev_email("Error getting random nums", 'Error getting random nums {num_randoms} {num_slots}'.format(num_randoms=num_randoms, num_slots=num_slots), [DEV_EMAIL])
                send_dev_pm("Error getting random nums", 'Error getting random nums {num_randoms} {num_slots}'.format(num_randoms=num_randoms, num_slots=num_slots))
        except Exception as err:
            logger.exception("Unknown error sending dev pm or email")

def getRdoRequest(num_randoms, num_slots):
    return {'jsonrpc': '2.0', 'method': 'generateSignedIntegers',
     'params': {'apiKey': RANDOM_ORG_API_KEY, 'n': num_randoms, 'min': 1, 'max': num_slots, 'replacement': False},
     'id': uuid.uuid4().hex}

def get_verification_random(random_dict):
    infoUrl = "null"
    if ('infoUrl' in random_dict):
        infoUrl = '"' + random_dict['infoUrl'] + '"'

    return '{{"method": "generateSignedIntegers",'\
    '"hashedApiKey": "{hashedApiKey}",'\
    '"n": {n},'\
    '"min": {min},'\
    '"max": {max},'\
    '"replacement": {replacement},'\
    '"base": {base},'\
    '"data": {data},'\
    '"completionTime": "{completionTime}",'\
    '"userData":null,'\
    '"license": {{"type":"{licenseType}", "text":"{licenseText}","infoUrl":{infoUrl}}},'\
    '"serialNumber": {serialNumber}}}'.format(
        hashedApiKey = random_dict['hashedApiKey'],
        n = random_dict['n'],
        min = random_dict['min'],
        max = random_dict['max'],
        replacement = str(random_dict['replacement']).lower(),
        base = random_dict['base'],
        data = random_dict['data'],
        completionTime = random_dict['completionTime'],
        serialNumber = random_dict['serialNumber'],
        licenseType = random_dict['license']['type'],
        licenseText = random_dict['license']['text'],
        infoUrl = infoUrl
    )

# =============================================================================
# MAIN
# =============================================================================

def main():
    logger.info("start")

    start_process = False

    if ENVIRONMENT == "DEV" and os.path.isfile(RUNNING_FILE):
        os.remove(RUNNING_FILE)
        logger.info("running file removed")

    if not os.path.isfile(RUNNING_FILE):
        create_running_file()
        start_process = True
    else:
        start_process = False
        logger.error("reddit post notifier already running! Will not start.")

    while start_process and os.path.isfile(RUNNING_FILE):
        logger.info("Start Main Loop")
        try:
            check_mentions()
            logger.info("End Main Loop")
        except Exception as err:
            logger.exception("Unknown Exception in Main Loop")
            try:
                send_dev_email("Unknown Exception in Main Loop", "Error: {exception}".format(exception = str(err)), [DEV_EMAIL])
                send_dev_pm("Unknown Exception in Main Loop", "Error: {exception}".format(exception = str(err)))
            except Exception as err:
                logger.exception("Unknown error sending dev pm or email")
        time.sleep(300)

    logger.info("end")

# =============================================================================
# RUNNER
# =============================================================================

if __name__ == '__main__':
    main()
