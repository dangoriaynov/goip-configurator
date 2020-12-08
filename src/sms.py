#!/usr/bin/env python
# coding=utf-8
import atexit
import multiprocessing
import re
import requests
import xml.etree.ElementTree as ET

from datetime import datetime
from random import randint
from smpplib import client as smpp_client, gsm, consts, exceptions
from src.const import SMPP_USER, SMPP_PORT, SMPP_SECRET, SENDER_PHONE, USSD_YEARLY_STATUS,\
    USSD_MONTHLY_STATUS, USSD_GENERAL_STATUS
from src.bot.common import bot
from src.utils import retry, current_time, log, sleep


def decode_msg(msg, encoding="utf-8"):
    try:
        return msg.decode(encoding)
    except UnicodeDecodeError as e:
        log.error("Exception while decoding SMS message: ")
        log.error(e)
        log.error("SMS message contents: %s" % msg)


def process_received_msg(pdu):
    frm = pdu.source_addr.decode()
    content = decode_msg(pdu.short_message)
    if not content or len(content) == 0:
        log.info("[Process Received SMS] Got long message. Using alternative logic")
        content = decode_msg(pdu.message_payload)
    content = content or "<empty>"
    log.info("[Process Received SMS] Message from: %s, content: %s" % (frm, content))
    bot.send("Отримано СМС від %s\n%s" % (frm, content), escape=True)


def process_sent_msg(pdu):
    log.info('[Process Sent SMS] Sent {} {} {}\n'.format(pdu.sequence, pdu.message_id, pdu.__dir__()))
    if pdu.status != 0:
        log.info("[Process Sent SMS] Error sending SMS")
        bot.send("Помилка при надсиланні СМС")
        return
    log.info("[Process Sent SMS] Sent successfully")
    bot.send("СМС надіслано")


class Sms:
    _all_processes = []
    CHECK_STATUS = '%s/default/en_US/send_status.xml?u=%s&p=%s'
    SEND_USSD = 'http://%s:%s@%s/default/en_US/sms_info.html?type=ussd'

    def __init__(self, url, uname, pwd, notify_module_is_up=False):
        self.url = url
        self.ip = url.split('://')[1] if url.startswith('http') else url
        self.uname = uname
        self.pwd = pwd
        log.info("[SMS Monitoring] Started")
        try:
            client = smpp_client.Client(self.ip, SMPP_PORT)
            client.set_message_received_handler(lambda pdu: process_received_msg(pdu))
            client.set_message_sent_handler(lambda pdu: process_sent_msg(pdu))
            client.connect()
            client.bind_transceiver(system_id=SMPP_USER, password=SMPP_SECRET)
            log.info("[SMS Monitoring] Attempting to listen...")
            process = multiprocessing.Process(target=client.listen)
            process.start()
            self._all_processes.append(process)
            log.info("[SMS Monitoring] Listening")
            if notify_module_is_up:
                bot.send("СМС моніторинг працює")
            self.client = client
        except exceptions.ConnectionError as e:
            bot.send("СМС моніторинг не працює.")
            raise Exception("SMS module is down", e)

    def send_sms(self, num, msg):
        log.info("[Send SMS] Number '%s', message '%s'" % (num, msg))
        # Two parts, UCS2, SMS with UDH
        parts, encoding_flag, msg_type_flag = gsm.make_parts(msg)
        for part in parts:
            pdu = self.client.send_message(
                source_addr_ton=consts.SMPP_TON_INTL,
                dest_addr_ton=consts.SMPP_TON_INTL,
                source_addr=SENDER_PHONE,
                destination_addr=num,
                short_message=part,
                data_coding=encoding_flag,
                esm_class=msg_type_flag,
                registered_delivery=True,
            )
            log.debug("[Send SMS] PDU Sequence # %d" % pdu.sequence)
        bot.send("Надсилаю СМС до %s\n%s" % num, msg)

    def send_ussd(self, num, bot_msg=False):
        if bot_msg:
            bot.send("Надсилаю USSD: %s" % num)
        key = '%d' % randint(10000, 1000000)
        requests.post(
            url=self.SEND_USSD % (self.uname, self.pwd, self.ip),
            data={'line1': '1', 'smskey': key, 'action': 'USSD', 'telnum': num, 'send': 'Send'}
        )
        return self.process_ussd_response(num, key)

    @retry(tries=10, delay=2, backoff=1)
    def process_ussd_response(self, num, key):
        result = requests.get(self.CHECK_STATUS % (self.url, self.uname, self.pwd))
        xml = ET.fromstring(result.content)
        id = xml.findall("id1")[0].text
        if id != key:
            raise Exception("Didn't find the proper key in the USSD response (expected='%s', got='%s')" % (key, id))
        status = xml.findall("status1")[0].text.strip()
        log.info("[USSD Response] Status of '%s' USSD code is '%s'" % (num, status))
        if status == "DONE":
            response = xml.findall("error1")[0].text
            if "GSM_LOGOUT" in response:
                raise Exception("GSM module is not ready yet")
            log.info("[USSD Response] Received: %s" % response)
            return response
        log.info("[USSD Response] Waiting for the USSD response")

    def close(self, force=False):
        if not self._all_processes:
            return
        log.info("[Close] Disconnecting the SMPP client")
        try:
            self.client.disconnect()
        except Exception as e:
            log.error(e)
        if not force:
            sleep(2)
        log.info("[Close] Terminating processes for SMS monitoring")
        for process in self._all_processes:
            process.terminate()


class SmsWrapper:
    sms = None
    _inited = False

    @classmethod
    def init(cls, url, uname, pwd, notify_module_is_up=False):
        cls.kill()
        try:
            cls.sms = Sms(url, uname, pwd, notify_module_is_up=notify_module_is_up)
            cls._inited = True
        except Exception as e:
            log.error(e)

    @classmethod
    def inited(cls):
        return cls._inited

    @classmethod
    def kill(cls, force=False):
        if cls.inited():
            cls._inited = False
        if cls.sms:
            cls.sms.close(force=force)
            cls.sms = None


atexit.register(SmsWrapper.kill, True)


@retry(tries=3)
def ussd_if_possible(code):
    return SmsWrapper.sms.send_ussd(code)


def send_sms(num, msg):
    if not SmsWrapper.inited():
        log.error("[Send SMS] Not able to send SMS to '%s' as SMS module is down" % num)
        return None
    return SmsWrapper.sms.send_sms(num=num, msg=msg)


def parse_ussd(code, regex, default=None):
    if not SmsWrapper.inited():
        log.error("[Parse USSD] Not able to call USSD '%s' as SMS module is down" % code)
        return None
    string = ussd_if_possible(code)
    if not string:
        log.error("[Parse USSD] Nothing returned from USSD command: %s" % code)
        return default
    m = re.search(regex, string)
    if not m:
        log.error("[Parse USSD] Unexpected response for regex: %s" % regex)
        return default
    result = list(m.groups())
    result.insert(0, True)
    return result


YEARLY_STATUS_REGEX = ".*?do ([\\d]{1,2}.[\\d]{1,2}.[\\d]{2}).*"
# Bezlimit v merezhi ta 500 MB pidkliucheni. Zalyshok: 500 MB, 29 hv ta 50 SMS po Ukraini za 1,5 grn v den'. Diie do 23.02.20...
MONTHLY_STATUS_REGEX = ".*? ([\\d]*) hv.*?Diie do ([\\d]{1,2}.[\\d]{1,2}.[\\d]{2}).*"
# Na vashem schete 9.22 grn. Tarif 'Some name'. Nomer deystvitelen do 20.12.2020. ...
BALANCE_REGEX = ".*? ([0-9.]*) grn. Tar[iy]{1}f '(.*?)'.*? do ([\\d]{1,2}.[\\d]{1,2}.[\\d]{4})"


def yearly_status():
    has_status, valid_till = parse_ussd(USSD_YEARLY_STATUS, YEARLY_STATUS_REGEX, [False, None])
    if has_status:
        log.info("[Yearly status] Found information: valid till '%s'" % valid_till)
        valid_till = datetime.strptime(valid_till, "%d.%m.%y")
    return has_status, valid_till


def monthly_status():
    has_status, minutes_left, valid_till = parse_ussd(USSD_MONTHLY_STATUS, MONTHLY_STATUS_REGEX, [False, None, None])
    valid_days = 0
    if has_status:
        log.info("[Monthly status] Found information: minutes left '%s', valid till '%s'" % (minutes_left, valid_till))
        valid_till_date = datetime.strptime(valid_till, "%d.%m.%y")
        valid_days = (valid_till_date - current_time()).days
    return has_status, minutes_left, valid_days


def balance():
    has_status, money, tariff, valid_till = parse_ussd(USSD_GENERAL_STATUS, BALANCE_REGEX, [False, 0, None, None])
    if has_status:
        log.info("[Balance] Found information: money '%s', tariff '%s', valid till '%s'" % (money, tariff, valid_till))
        money = float(money)
        valid_till = datetime.strptime(valid_till, "%d.%m.%Y")
    return has_status, money, tariff, valid_till
