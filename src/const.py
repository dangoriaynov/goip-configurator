#!/usr/bin/env python
# coding=utf-8
import os

# BEGIN SECRETS SECTION

try:
    from src.secret.secrets import *
except ImportError:
    # whether it is PROD or DEV env
    IS_PROD = False
    # GoIP IP address
    IP = "192.168.1.1"
    # SIP login
    SIP = "123456"
    # SIP password
    SIP_PASS = "SipProviderPass"
    # Phone number assigned to the caller
    SENDER_PHONE = "+380501234567"
    # GoIP admin username
    USER = "admin"
    # GoIP admin password
    PASS = "admin"
    # SMPP username
    SMPP_USER = "admin"
    # SMPP password
    SMPP_SECRET = "admin"
    # Telegram chat key
    TEL_KEY = "12321333:Abccdasddd"
    # Telegram chat id
    TEL_CHAT = "-1231231233"
    # Telegram users allowed to interact with the bot
    ALLOWED_USERS = ['@username1', '@username2']
    raise NotImplementedError("Please specify real values to the consts listed above")

# END SECRETS SECTION

# platform we are running the script on
RUNNING_ON = sys.argv[1].replace("-", "") if len(sys.argv) > 1 else "raspberry"

# whether screenshots should be stored on browser actions (use force=True to override)
STORE_SCREENS = not IS_PROD

# Seconds to sleep between 'is caller working?' verifications
GOIP_MONITOR_SLEEP_SECONDS = 10 * 60 if IS_PROD else 1 * 60

# Seconds to sleep in-between call status check cycles
LAST_CALL_SLEEP_SECONDS = 5 if IS_PROD else 10

# Default date format
DATE_FORMAT = "%d.%m.%Y"

# Default datetime format to be used
DATETIME_FORMAT = "%d.%m.%Y %H:%M:%S"

# Default log level of this script
LOG_LEVEL = "INFO"

# Default log output filename/location
LOG_NAME = "out.log"

# SMPP port to be used for SMS monitoring
SMPP_PORT = 7777

# Default GoIP admin username - to be used after caller is reset to defaults
DEFAULT_GOIP_PWD = "admin"

# USSD to get balance info
USSD_GENERAL_STATUS = "*101#"

# USSD to get monthly info (monthly minutes left etc)
USSD_MONTHLY_STATUS = "*101*4#"

# USSD to get yearly info (valid till, yearly paid etc)
USSD_YEARLY_STATUS = "*365*1#"

# Current application dir
CUR_DIR = os.path.realpath(os.getcwd())

# Path to the webdriver executables - different platforms have different locations
DRIVER_EXECUTABLES = {"raspberry": CUR_DIR + "/phantomjs",
                      "windows": CUR_DIR + "\\phantomjs.exe",
                      "mac": CUR_DIR + "/phantomjs"}

# Path to the currently used webdriver executable
DRIVER_EXECUTABLE = DRIVER_EXECUTABLES.get(RUNNING_ON)

# Phrases used by Telegram chat bot to tell that app is now started
GREETING_PHRASES = ["Знову на дроті", "Здоровенькі були!", "Охо-хо!", "Викликали? Вже тут", "Алінці - привіт!",
                    "Привітики-пістолітики!", "Я дзвонилка хоч куди", "Відкривай ворота", "З високосним роком вас!",
                    "Поїзд з обліпихою вже тут", "Кохання...та-та-та-та", "Сподіваюсь, що ви хрумали",
                    "І хто ото познімав всі фірточки?", "Ех Матрьона...", "Я знову в ділі", "Мої вітання!",
                    "Обіймемось?", "Вкусняхи в студію!", "Я працюю - дивина та й годі!", "Тринь - ісполнєно!"]