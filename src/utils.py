#!/usr/bin/env python
# coding=utf-8
import time
from datetime import datetime
from logging import StreamHandler
from logging.handlers import TimedRotatingFileHandler
from random import randint
from functools import wraps

from src.const import LOG_LEVEL, LOG_NAME, CUR_DIR


def set_log_level():
    import logging as log
    sh = StreamHandler()
    sh.setLevel(LOG_LEVEL)  # output to console with specified LOG LEVEL
    fh = TimedRotatingFileHandler("{0}/{1}".format(CUR_DIR, LOG_NAME), when="d", interval=15, backupCount=3)
    fh.setLevel(log.DEBUG)  # output to file with DEBUG log level always
    log.basicConfig(
        level=log.NOTSET,
        format="%(asctime)s [%(threadName)-12.12s] %(message)s",
        handlers=[
            sh,
            fh
        ])
    return log.getLogger("Goip Monitor")


log = set_log_level()


def passed_more_that_sec(time_from, sec):
    return time_from and sec and (current_time() - time_from).seconds > sec


def current_time():
    return datetime.now()


def current_date():
    return datetime.today()


def sleep(seconds, print_log=True):
    if print_log:
        log.info("[Sleep] Sleeping for %d seconds" % seconds)
    time.sleep(seconds)


def seconds_to_time_str(seconds_all, no_seconds=False):
    days = seconds_all // 3600 // 24
    hours = seconds_all // 3600 - days * 24
    minutes = seconds_all // 60 - hours * 60 - days * 24 * 60
    seconds = seconds_all % 60
    days_str = "%s дн " % days if days else ""
    hours_str = "%s год " % hours if hours or days else ""
    minutes_str = "%s хв " % minutes if minutes or hours or days else ""
    seconds_str = "%s сек" % seconds if not no_seconds or seconds_all < 60 else ""
    return "%s%s%s%s" % (days_str, hours_str, minutes_str, seconds_str)


def random_list_item(phrases):
    if len(phrases) == 0:
        log.warning("[Random list item] List is empty!")
        return
    return phrases[randint(0, len(phrases) - 1)]


def safe(msg=None):
    """Call the decorated function and log any exception thrown but do not interrupt the program.
    """
    def deco_safe(f):
        @wraps(f)
        def f_safe(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                try:
                    log.error("[Safe] Exception occurred while running safe() method:")
                    log.error(e)
                    if msg:
                        from src.bot.common import bot
                        bot.send(msg)
                except Exception as e1:
                    log.error("[Safe] Some really bad exception has happened while handling method exception:")
                    log.error(e1)
        return f_safe  # true decorator
    return deco_safe


def retry(ex=None, tries=4, delay=3, backoff=2):
    """Retry calling the decorated function using an exponential backoff.
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    """
    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            res = None
            while mtries > 1:
                if ex:
                    try:
                        return f(*args, **kwargs)
                    except ex:
                        pass
                else:
                    res = f(*args, **kwargs)
                    if res is not None:
                        return res
                log.info("[Retry Deco] Retrying in %d seconds..." % mdelay)
                time.sleep(mdelay)
                mtries -= 1
                mdelay *= backoff
            return res
        return f_retry  # true decorator
    return deco_retry
