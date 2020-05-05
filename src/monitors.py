#!/usr/bin/env python
# coding=utf-8
import re

from src.db import vs
from src.browser import BrowserWrapper, NotLoggedIn
from src.bot.common import bot
from src.bot.personal import RebootRequest, ResetRestoreRequest, BalanceRequest, pbot, SendUssdRequest, SendSmsRequest
from src.const import DEFAULT_GOIP_PWD, SMPP_USER, SMPP_SECRET, SENDER_PHONE, \
    GOIP_MONITOR_SLEEP_SECONDS, LAST_CALL_SLEEP_SECONDS, DATE_FORMAT, GREETING_PHRASES
from src.sms import balance, monthly_status, yearly_status, SmsWrapper
from src.utils import random_list_item, current_time, seconds_to_time_str, log, passed_more_that_sec, \
    current_date, sleep


def reset_daily_values(money=0.0):
    log.info("[Reset daily values] Setting initial values")
    if not money:
        _, money, _, _ = balance()
    vs.set_current_balance(money)
    vs.increase_overall_call_duration(vs.daily_calls_duration())
    vs.set_daily_calls_duration(0)
    vs.set_daily_fixed_times(0)
    vs.set_daily_ok_calls_amount(0)
    vs.set_daily_failed_calls_amount(0)


def daily_balance_diff(money=0.0):
    if not money:
        _, money, _, _ = balance()
    diff = money - vs.current_balance()
    res = "+%s" % diff if diff > 0 else str(diff)
    return diff != 0, res


def daily_status(scheduled_run=True):
    has_balance_info, money, tariff, number_valid_till = balance()
    has_monthly_info, monthly_minutes_left, monthly_valid_days = monthly_status()
    has_yearly_info, yearly_valid_till = yearly_status()
    string = ""
    ok_calls_amt = vs.daily_ok_calls_amount()
    failed_calls_amt = vs.daily_failed_calls_amount()
    all_calls_amt = ok_calls_amt + failed_calls_amt
    calls_duration = vs.daily_calls_duration()
    fixed_times = vs.daily_fixed_times()
    today_is_sunday = current_date().strftime("%w") == "0"
    # daily calls status
    if all_calls_amt > 0:
        calls_stats = " (%d%%)" % (100 * ok_calls_amt / all_calls_amt)
    else:
        calls_stats = ""
    if calls_duration:
        duration_str = seconds_to_time_str(calls_duration, no_seconds=True)  # omit the seconds part
        duration_str = "%s%s" % (duration_str, calls_stats)
        if scheduled_run:
            vs.increase_weekly_call_duration(calls_duration)
    else:
        duration_str = "не було"
    string += "Розмов %s\n" % duration_str
    # weekly calls status
    weekly_calls_duration = vs.weekly_calls_duration()
    if not scheduled_run:  # as we do not increment weekly calls duration if it's a not scheduled_run
        weekly_calls_duration += calls_duration
    if today_is_sunday or not scheduled_run:  # if it's Sunday or on-demand info request
        duration_str = seconds_to_time_str(weekly_calls_duration, no_seconds=True)  # omit the seconds part
        string += "За тиждень %s\n" % duration_str
    if has_balance_info:
        string += "На рахунку %s грн" % money
        has_money_diff, money_diff = daily_balance_diff(money=money)
        if has_money_diff:
            string += " (%s грн)" % money_diff
        string += "\n"
    if has_monthly_info:
        days_add = "на %s дні(в)" % monthly_valid_days if monthly_valid_days > 0 else "до сьогодні"
        string += "%s хв %s\n" % (monthly_minutes_left, days_add)
    if fixed_times:
        string += "<b>Полагоджено %s раз(и)</b>\n" % fixed_times
    if tariff:
        string += "Тариф %s\n" % tariff
    if number_valid_till or yearly_valid_till:
        if yearly_valid_till and yearly_valid_till < number_valid_till:
            valid_till = yearly_valid_till
        else:
            valid_till = number_valid_till or yearly_valid_till  # as 1 might be None
        days_left = (valid_till - current_time()).days
        if days_left < 10:
            string += "<b>Поповни! Лишилось %s дні(в)</b>\n" % days_left
        string += "Рік/номер до %s\n" % valid_till.strftime(DATE_FORMAT)
    if scheduled_run:
        reset_daily_values(money=money)
        if today_is_sunday:
            vs.set_weekly_calls_duration(0)
    return string


class GoipMonitor:
    goip_slept_at = None
    voip_connection_status = None

    def __init__(self, url, uname, pwd, sip, spwd):
        if not url.startswith("http"):
            url = "http://%s" % url
        self.url = url
        self.uname = uname
        self.pwd = pwd
        self.sip = sip
        self.spwd = spwd
        self.init_browser()
        self.init_sms()
        # if daily call duration is from today
        if vs.daily_calls_duration(field="date").date() != current_date().date():
            vs.increase_weekly_call_duration(vs.daily_calls_duration())  # as we will reset this value
            reset_daily_values()  # set default values for the daily status
        else:
            log.info("[GoipMonitor] Recent restart - do not reset daily calls duration.")

    def send_greenting(self):
        if passed_more_that_sec(vs.monitor_slept_at(notify=True), 30*60):  # if not restarted within 20-30 minutes
            bot.send(random_list_item(GREETING_PHRASES))
        else:
            log.info("[GoipMonitor] Regular restart - no greeting was sent")

    def init_browser(self, pwd=None):
        try:
            BrowserWrapper.init(self.url, self.uname, pwd or self.pwd)
        except NotLoggedIn as e:
            log.error("[Init browser] Error in init_browser: %s" % e)
            if pwd != DEFAULT_GOIP_PWD:
                log.warning("[Init Browser] Logging in using default password")
                BrowserWrapper.init(self.url, self.uname, DEFAULT_GOIP_PWD)
        BrowserWrapper.b.driver.refresh()

    def init_sms(self, notify=False):
        SmsWrapper.init(self.url, self.uname, self.pwd, notify_module_is_up=notify)

    def send_caller_status(self, status):
        seconds_up_sec = BrowserWrapper.b.uptime_sec()
        up_str = seconds_to_time_str(seconds_up_sec)
        talk_time_sec = vs.overall_call_duration()
        talk_str = seconds_to_time_str(talk_time_sec)
        BrowserWrapper.b.screenshot(name="before-reset", force=True)
        if status:
            status = "Дзвонилка <b>не фуричить</b>.\n%s\n" % status
        bot.send("%sЗапущена вже %s\nНаговорили %s\nПереналаштовую..." % (status, up_str, talk_str))

    def reset_and_restore(self):
        last_reg_status = vs.last_reg_status()
        log.info("[Reset and restore] Caller stopped working. %s" % last_reg_status)
        self.send_caller_status(last_reg_status)
        vs.set_overall_call_duration(0)  # reset it as caller is not working
        self.reset_config()
        self.restore_config()
        if self.statuses_ok():
            log.info("[Reset and restore] Caller is working now")
            bot.send("Дзвонилка <b>працює</b>. Просто крутизна!")
        else:
            log.info("[Reset and restore] Caller is not working after fix")
            bot.send("Дзвонилка <b>не працює</b>. Спробую ще пізніше.")

    def statuses_ok(self):
        log.info("[Statuses ok] Checking")
        b = BrowserWrapper.b
        sim = b.by_id("l1_gsm_sim").text.strip()
        gsm = b.by_id("l1_gsm_status").text.strip()
        voip = b.by_id("l1_status_line").text.strip()
        vs.set_last_reg_status(None)  # reset value
        if voip == "401":
            log.error("[Statuses ok] Incorrect SIP username/password specified.")
            # try to fix fix-able issue only once per day as more attempts are often useless
            if vs.last_date_error_notified().date() == current_time().date():
                return True  # do not fix
            vs.set_last_date_error_notified(current_time())
            vs.set_last_reg_status("Помилка реєстрації VoIP. Невірний логін/пароль (код %s)" % voip)
            return False  # try to fix
        if voip == "403":
            log.error("[Statuses ok] Error 403. No easy remedy for this")
            vs.set_last_reg_status("Невідома помилка (код %s)" % voip)
        if voip != "Y":
            log.error("[Statuses ok] VoIP registration failed (status = '%s')." % voip)
            vs.set_last_reg_status("Помилка реєстрації VoIP (код %s)" % voip)
            return False  # try to fix
        if sim != "Y":
            log.error("[Statuses ok] SIM not found. No easy remedy for this")
            vs.set_last_reg_status("SIM не знайдено")
        if gsm != "Y":
            log.error("[Statuses ok] No GSM network. No easy remedy for this")
            vs.set_last_reg_status("Помилка реєстрації GSM")
        vs.set_last_date_error_notified(None)
        return True  # do not try to fix

    def reboot(self):
        log.info("[Reboot] Rebooting caller")
        SmsWrapper.kill()
        bot.send("Перезавантажую дзвонилку.")
        BrowserWrapper.b.go_relative_url("reboot.html")
        sleep(30)
        self.init_browser()
        self.init_sms(notify=True)
        log.info("[Reboot] Finished reboot")
        bot.send("Перезавантажено дзвонилку.")

    def reset_config(self):
        log.info("[Reset config] Re-setting")
        # as GoIP's SMPP is not started after configuration is reset
        SmsWrapper.kill()
        BrowserWrapper.b.go_relative_url("reset_config.html")
        sleep(20)
        # login with default password
        self.init_browser(pwd=DEFAULT_GOIP_PWD)

    def restore_config(self):
        log.info("[Restore config] Restoring")
        b = BrowserWrapper.b
        b.open_menu("Configurations")
        b.set_text(b.by_id("time_zone"), "GMT+2")
        b.set_text(b.by_id("ntp_server"), "0.ua.pool.ntp.org")
        b.by_id("auto_reboot_disable").click()
        b.by_id("ivr_enable_disable").click()
        b.by_id("smpp_enable_enable").click()
        b.set_text(b.by_id("smpp_id"), SMPP_USER)
        b.set_text(b.by_id("smpp_key"), SMPP_SECRET)
        b.set_text(b.by_id("dtmf_min_gap"), "200")
        b.save()
        b.open_menu("Network")
        b.set_select("pc_port_select", "Bridge mode")
        b.save()
        b.open_menu("Basic VoIP")
        b.set_text(b.by_id("sip_auth_id"), self.sip)
        b.set_text(b.by_id("sip_auth_passwd"), self.spwd)
        b.set_text(b.by_id("sip_registrar"), "sip.zadarma.com")
        b.set_text(b.by_id("sip_phone_number"), self.sip)
        b.set_text(b.by_id("sip_display_name"), self.sip)
        b.save()
        b.open_menu("Advance VoIP")
        b.set_select("sip_local_port_mode_select", "Fixed")
        b.set_select("sip_183_select", "SIP 180")
        b.save()
        b.open_menu("Media")
        b.expand_items("Audio Codec Preference")
        b.disable_codec("g729a")
        b.disable_codec("g729ab")
        b.disable_codec("g7231")
        b.move_up_codec("g729", 2)
        b.save()
        b.open_menu("Call Out")
        b.set_text(b.by_id("gsm_outc_noans_t"), "60")
        b.save()
        b.open_menu("Call Out Auth")
        b.set_select("line1_fw2pstn_auth_mode_select", "Whitelist")
        b.expand_items("Whitelist/Blacklist")
        b.set_text(b.by_id("l1_voip_trust_num1"), "419522")
        b.set_text(b.by_id("l1_voip_trust_num2"), "549950")
        b.set_text(b.by_id("l1_voip_trust_num3"), "685171")
        b.set_text(b.by_id("l1_voip_trust_num4"), "752227")
        b.save()
        b.open_menu("Call In")
        b.by_id("line1_fw_to_voip_disable").click()
        b.save()
        b.open_menu("SIM")
        b.by_id("gprs_disable").click()
        b.by_id("expiry_m_enable").click()
        b.set_text(b.by_id("line1_gsm_num"), SENDER_PHONE)
        b.set_text(b.by_id("line1_gsm_pin2"), "9819")
        b.by_id("line1_exp_drop_disable").click()
        b.save()
        b.open_menu("Tools")
        b.open_menu("User Management")
        parent = "//table[//td[text()='Administration Level']]//form[@name='form2']//"
        xpath = parent + "input[@name='%s']"
        b.set_text(b.by_xpath(xpath % "passwd"), self.pwd)
        b.set_text(b.by_xpath(xpath % "confirm_passwd"), self.pwd)
        b.by_xpath(parent + "input[@type='submit' and @value='Change']").click()
        sleep(10)
        self.init_browser()
        self.init_sms()
        vs.increase_daily_fixed_times(1)

    def goip_monitor(self):
        # we couldn't afford sleep(600) because we are working with browser in the single thread
        # instead - just skip method' body till the sleep time is elapsed
        if self.goip_slept_at and not passed_more_that_sec(self.goip_slept_at, GOIP_MONITOR_SLEEP_SECONDS):
            return True

        cdr_started = BrowserWrapper.b.by_id("l1_cdrt").text.strip()
        if cdr_started.startswith("1970-01"):
            log.error("[GoipMonitor] Have internal GoIP issue (1970 year at clock).")
            if vs.last_date_cdr_restart() == current_time().date():  # if we had the same problem today
                bot.send("Переналаштовую дзвонилку бо вона ґеґнула (1970 рік надворі)!")
                self.reset_and_restore()
            else:
                vs.set_last_date_cdr_restart(current_time().date())  # if this is the first problem occurrence
                bot.send("Перезавантажую дзвонилку бо вона знову ні-гугу (1970 рік надворі)!")
                self.reboot()
            # open the 'Status' tab again to support the logic in rest of the cycle
            BrowserWrapper.b.open_menu("Status")
            # just waiting for the fix to be applied. Nothing could be done now
            return False
        # reason for the status check is doing fix only if GoIP problem persists for >1 cycle
        goip_is_working = self.statuses_ok()
        if not goip_is_working and vs.last_reg_status() == self.voip_connection_status:
            self.reset_and_restore()
            # open the 'Status' tab again to support the logic in rest of the cycle
            BrowserWrapper.b.open_menu("Status")
        self.voip_connection_status = vs.last_reg_status()
        self.goip_slept_at = current_time()  # we have this in-memory var to decrease amt of calls to the DB
        vs.set_monitor_slept_at(self.goip_slept_at)  # we are using this value as heartbeat for the whole GoIP monitor
        log.info("[GoipMonitor] Sleeping for %d sec..." % GOIP_MONITOR_SLEEP_SECONDS)
        if not goip_is_working:  # just waiting for the fix to be applied. Nothing could be done now
            log.error("[GoipMonitor] Patient is not ok. Will check again soon.")
            return False
        return True


class CallMonitor:
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    ALERTING = "ALERTING"
    DIALING = "DIALING"
    CONNECTED = "CONNECTED"
    STARTING_CALL_STATUSES = [ALERTING, DIALING, ACTIVE]
    STATUS_TO_NUMBER_REGEX = "(%s|%s|%s)\\:([+0-9]*)" % (DIALING, CONNECTED, ALERTING)
    STATUS_LOG_MSG = {
        ACTIVE: ["Typing the number", "Набір номеру"],
        ALERTING: ["Alerting the number", "Підключення до {number}"],
        DIALING: ["Dialing the number", "Дзвоник до {number}"]}
    ERROR_PHRASES = [" і навдача...", " тю-тю", " та няма късмет", " і відкрилась ще одна чакра",
                     ", тепер піду посплю", ". І нашо ото було?", ". Є чим гордитися",
                     ". А цьом буде?", ", проте питання лишилось відкритим", ". Тепер сиджу, як абізяна..."]
    status = None
    status_changed = False
    dialing_started = None
    call_started = None
    call_number = None
    msg_call_status = None
    last_called_number = None
    last_msg = None

    def __init__(self, goip):
        self.goip = goip
        self.daily_status_sent_at = vs.daily_status_sent()

    def monitor(self):
        log.info("[CallMonitor] Started monitor")
        BrowserWrapper.b.open_menu("Status")
        waiting_from = None
        while True:
            if pbot.has_request():
                skip_processing = False
                request = pbot.request
                log.info("[CallMonitor] Has personal bot request: %s" % request)
                # reboot and reset/restore are still possible while in the call
                # as we have a confirmation message before running each of them
                if self.call_or_dialing_started():
                    if isinstance(request, BalanceRequest)\
                            or isinstance(request, SendSmsRequest)\
                            or isinstance(request, SendUssdRequest):
                        log.info("[CallMonitor] Could not process the request while in a call. Waiting...")
                        skip_processing = True
                if isinstance(request, RebootRequest) or isinstance(request, ResetRestoreRequest):
                    waiting_from = None
                if not skip_processing:
                    log.info("[CallMonitor] Processing personal bot request")
                    pbot.process_request(self.goip)
                    log.info("[CallMonitor] Processed personal bot request")
                    BrowserWrapper.b.open_menu("Status")
            # send daily status every day once at 23:XX when no-one is using GoIP caller
            if current_time().hour == 23 and not self.call_or_dialing_started() and\
                    (not self.daily_status_sent_at or self.daily_status_sent_at.date() != current_date().date()):
                self.daily_status_sent_at = current_time()  # using in-memory var to decrease amt of calls to DB
                vs.set_daily_status_sent(self.daily_status_sent_at)
                bot.send(daily_status())
            # this should be checked every time, so no var defined above
            sleep_for_sec = 2 if self.call_or_dialing_started() else LAST_CALL_SLEEP_SECONDS
            # if not authorised for < 5 minutes - just wait for this issue to get fixed (with reset/restore?)
            if not BrowserWrapper.b.is_authorized() and not passed_more_that_sec(waiting_from, 5 * 60):
                log.warning("[CallMonitor] Browser is not ok - session is not authorised")
                if waiting_from is None:
                    waiting_from = current_time()
                sleep(sleep_for_sec)
                continue
            waiting_from = None
            # this is the way to get up-to-day info from the page
            BrowserWrapper.b.driver.refresh()
            if self.goip.goip_monitor():  # if all is fine with GoIP
                self.call_monitor()  # run call monitor logic
            else:
                log.info("[CallMonitor] GoIP monitor is not ok")
            sleep(sleep_for_sec, print_log=False)

    def calculate_status(self):
        def set_number(raw_status):
            m = re.search(self.STATUS_TO_NUMBER_REGEX, raw_status)
            if not m or len(m.groups()) < 2:
                return
            number = m.group(2)
            if number.find("00") == 0:  # replace '00' with '+' in the beginning
                number = "+%s" % number[2:]
            self.call_number = number

        def set_status(value):
            self.status_changed = False
            if self.status != value:
                self.status = value
                self.status_changed = True
        raw_status_string = BrowserWrapper.b.by_id("l1_line_state").text.strip()
        # IDLE -> just waiting for the call to happen
        if raw_status_string == "IDLE":
            set_status(self.IDLE)
        # ACTIVE -> typing the number
        elif raw_status_string == "ACTIVE":
            set_status(self.ACTIVE)
        # ALERTING -> callee phone is ringing
        elif raw_status_string.startswith("ALERTING"):
            set_status(self.ALERTING)
        # DIALING -> sending request through the VoIP / GSM network
        elif raw_status_string.startswith("DIALING"):
            set_status(self.DIALING)
        # CONNECTED -> actually speaking with the number
        elif raw_status_string.startswith("CONNECTED"):
            set_status(self.CONNECTED)
        else:
            raise Exception("Unknown raw status: %s" % raw_status_string)
        set_number(raw_status_string)

    def any_call_number(self):
        return self.last_called_number or self.call_number or "'невідомо кого'"

    def bot_message(self, text):
        text = text.format(number=self.any_call_number())
        if self.last_msg:
            return bot.edit(msg=self.last_msg, text=text)
        return bot.send(text=text)

    def call_or_dialing_started(self):
        return self.call_started or self.dialing_started

    def start_dialing(self):
        self.dialing_started = current_time()
        try:
            log_msg, self.msg_call_status = self.STATUS_LOG_MSG.get(self.status)
        except TypeError as e:  # if call already started
            log.warning("[Start call] Exception getting message from call status: %s" % e)
            log_msg, self.msg_call_status = self.STATUS_LOG_MSG.get(self.DIALING)
        log.info("[Start call] %s" % log_msg)
        if self.status_changed:
            self.last_msg = self.bot_message(self.msg_call_status)

    def start_call(self):
        # this could happen when previous call ended and new started in-between check cycles
        if self.call_started and self.call_number != self.last_called_number:
            self.finish_call()
        # if we missed dialing statuses because of slow cycles
        if not self.dialing_started:
            self.start_dialing()
        # start actual call
        if not self.call_started:
            log.info("[Process call] Started call to %s" % self.call_number)
            self.last_msg = self.bot_message("Говоримо з %s" % self.call_number)
            self.call_started = current_time()
            self.last_called_number = self.call_number

    def finish_call(self):
        number = self.any_call_number()
        log.info("[Finish call] Processing call end for '%s'" % number)
        started_when = self.call_or_dialing_started()
        log.info("[Finish call] Call started at %s" % started_when)
        seconds = (current_time() - started_when).seconds
        log.info("[Finish call] Overall call duration is %s seconds" % seconds)
        duration_str = seconds_to_time_str(seconds, no_seconds=(seconds > 3600))
        log.info("[Finish call] Call to %s ended (%s)" % (number, duration_str))
        if self.call_started:
            text = "Дзвоник до %s - %s" % (number, duration_str)
            vs.increase_daily_call_duration(seconds)
            vs.increase_daily_ok_calls_amount(1)
        else:
            if self.msg_call_status:
                text = self.msg_call_status + random_list_item(self.ERROR_PHRASES)
            else:
                text = "Ймовірно невдалий дзвоник до {number}"
            vs.increase_daily_failed_calls_amount(1)
        self.bot_message(text)
        self.dialing_started = self.call_started = self.last_called_number = self.msg_call_status = self.last_msg = None

    def call_monitor(self):
        self.calculate_status()
        if self.status == self.IDLE:
            if self.call_or_dialing_started():
                self.finish_call()  # back to idle
            return
        log.info("[Monitor call status] Status string = '%s'" % self.status)
        if self.status in self.STARTING_CALL_STATUSES:
            self.start_dialing()
        if self.status == self.CONNECTED:
            self.start_call()
