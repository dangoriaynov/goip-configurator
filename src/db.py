#!/usr/bin/env python
# coding=utf-8
import atexit
from datetime import datetime
from sqlite3worker import Sqlite3Worker

from src.const import CUR_DIR, DATETIME_FORMAT
from src.utils import log


class DBStorage:
    create_table = """ CREATE TABLE IF NOT EXISTS db_dict (
                        id integer PRIMARY KEY,
                        key text NOT NULL UNIQUE,
                        value text,
                        date text); """
    drop_index = " DROP INDEX IF EXISTS idx_dbdict_key; "
    create_index = """ CREATE UNIQUE INDEX IF NOT EXISTS idx_dbdict_key 
                        ON db_dict (key); """

    def __init__(self, recreate=False):
        database = r"%s/sqlite.db" % CUR_DIR  # this will create separate DB for each platform used
        log.info("[DB] Start the module")
        self.conn = Sqlite3Worker(database)
        self.conn.execute(self.create_table)
        if recreate:
            self.conn.execute(self.drop_index)
        self.conn.execute(self.create_index)

    def get(self, key, field="value", all_fields=False, notify=True):
        if notify:
            log.info("[DB] Get value for key '%s'" % key)
        sql = ''' SELECT id, key, value, date
                  FROM db_dict
                  WHERE key = ?'''
        results = self.conn.execute(sql, (key,))
        id, _, value, date = results[0] if results else [None, None, None, None]
        if all_fields:
            result = {k: v for k, v in zip(["id", "value", "date"], [id, value, date])}
        elif field == "value":
            result = value
        else:
            if field == "id":
                result = id
            elif field == "date":
                result = date
            else:
                raise Exception("Incorrect field name expected: %s" % field)
        if notify:
            log.info("[DB] Obtained value for key '%s' == '%s'" % (key, result))
        return result

    def update(self, key, value, date=datetime.now()):
        log.info("[DB] Update value for key '%s' (new value '%s')" % (key, value))
        sql = ''' UPDATE db_dict
                  SET value = ?, date = ?
                  WHERE key = ?'''
        self.conn.execute(sql, (value, date, key))

    def insert(self, key, value, date=datetime.now()):
        sql = ''' REPLACE INTO db_dict(key, value, date)
                  VALUES(?, ?, ?) '''
        self.conn.execute(sql, (key, value, date))

    def set(self, key, value, date=datetime.now()):
        log.info("[DB] Set value for key '%s' = '%s'" % (key, value))
        self.insert(key=key, value=value, date=date)

    def delete(self, key):
        log.info("[DB] Delete contents associated with key '%s'" % key)
        sql = 'DELETE FROM db_dict WHERE key = ?'
        self.conn.execute(sql, (key,))

    def purge(self):
        log.info("[DB] Purge contents")
        sql = 'DELETE FROM db_dict'
        self.conn.execute(sql)

    def close(self):
        if self.conn:
            self.conn.close()


class MemoryStorage:
    vals = dict()

    def get(self, key):
        return self.vals.get(key) if key in self.vals.keys() else None

    def set(self, key, value):
        self.vals.update({key: value})

    def close(self):
        pass


class Storage:
    try:
        _db = DBStorage()
    except Exception as e:
        log.error("[Storage] Error while init of DB storage: %s. Using in-memory one" % e)
        _db = MemoryStorage()
    _DAILY_CALLS_DURATION = "DAILY_CALL_DURATION"
    _WEEKLY_CALLS_DURATION = "WEEKLY_CALLS_DURATION"
    _OVERALL_CALLS_DURATION = "OVERALL_CALL_DURATION"
    _DAILY_FIXED_TIMES = "DAILY_FIXED_TIMES"
    _DAILY_OK_CALLS_AMOUNT = "DAILY_CALLS_AMOUNT"
    _DAILY_FAILED_CALLS_AMOUNT = "DAILY_FAILED_CALLS_AMOUNT"
    _LAST_TIME_ERROR_NOTIFIED = "LAST_TIME_ERROR_NOTIFIED"
    _INITIAL_BALANCE = "INITIAL_BALANCE"
    _LAST_REG_STATUS = "LAST_REG_STATUS"
    _LAST_CDR_START = "LAST_CDR_START"
    _MONITOR_SLEPT_AT = "MONITOR_SLEPT_AT"
    _DAILY_STATUS_SENT = "DAILY_STATUS_SENT"

    def daily_calls_duration(self, default=0, field="value"):
        result = self._db.get(self._DAILY_CALLS_DURATION, field) or default
        if field == "value":
            return int(result)
        elif field == "date":
            return datetime.strptime(result, '%Y-%m-%d %H:%M:%S.%f')
        return result

    def set_daily_calls_duration(self, value):
        return self._db.set(self._DAILY_CALLS_DURATION, int(value))

    def increase_daily_call_duration(self, value):
        duration = int(self.daily_calls_duration(default=0))
        value = int(value)
        self.set_daily_calls_duration(duration + value)

    def weekly_calls_duration(self, default=0):
        return int(self._db.get(self._WEEKLY_CALLS_DURATION) or default)

    def set_weekly_calls_duration(self, value):
        return self._db.set(self._WEEKLY_CALLS_DURATION, int(value))

    def increase_weekly_call_duration(self, value):
        duration = int(self.weekly_calls_duration(default=0))
        value = int(value)
        self.set_weekly_calls_duration(duration + value)

    def overall_call_duration(self, default=0):
        return int(self._db.get(self._OVERALL_CALLS_DURATION) or default)

    def set_overall_call_duration(self, value):
        return self._db.set(self._OVERALL_CALLS_DURATION, int(value))

    def increase_overall_call_duration(self, value):
        duration = self.overall_call_duration(default=0)
        value = int(value)
        self.set_overall_call_duration(duration + value)

    def daily_fixed_times(self, default=0):
        return int(self._db.get(self._DAILY_FIXED_TIMES) or default)

    def set_daily_fixed_times(self, value):
        return self._db.set(self._DAILY_FIXED_TIMES, int(value))

    def increase_daily_fixed_times(self, value):
        fixed = self.daily_fixed_times(default=0)
        value = int(value)
        self.set_daily_fixed_times(fixed + value)

    def daily_ok_calls_amount(self, default=0):
        return int(self._db.get(self._DAILY_OK_CALLS_AMOUNT) or default)

    def set_daily_ok_calls_amount(self, value):
        return self._db.set(self._DAILY_OK_CALLS_AMOUNT, int(value))

    def increase_daily_ok_calls_amount(self, value):
        calls = self.daily_ok_calls_amount(default=0)
        value = int(value)
        self.set_daily_ok_calls_amount(calls + value)

    def daily_failed_calls_amount(self, default=0):
        return int(self._db.get(self._DAILY_FAILED_CALLS_AMOUNT) or default)

    def set_daily_failed_calls_amount(self, value):
        return self._db.set(self._DAILY_FAILED_CALLS_AMOUNT, int(value))

    def increase_daily_failed_calls_amount(self, value):
        calls = self.daily_failed_calls_amount(default=0)
        value = int(value)
        self.set_daily_failed_calls_amount(calls + value)

    def last_date_error_notified(self, default=None):
        value = self._db.get(self._LAST_TIME_ERROR_NOTIFIED) or default
        return datetime.strptime(value, DATETIME_FORMAT) if value else value

    def set_last_date_error_notified(self, value):
        return self._db.set(self._LAST_TIME_ERROR_NOTIFIED, value.strftime(DATETIME_FORMAT) if value else value)

    def last_date_cdr_restart(self, default=None):
        value = self._db.get(self._LAST_CDR_START) or default
        return datetime.strptime(value, DATETIME_FORMAT) if value else value

    def set_last_date_cdr_restart(self, value):
        return self._db.set(self._LAST_CDR_START, value.strftime(DATETIME_FORMAT) if value else value)

    def monitor_slept_at(self, default=None, notify=False):
        value = self._db.get(self._MONITOR_SLEPT_AT, notify=notify) or default
        return datetime.strptime(value, DATETIME_FORMAT) if value else value

    def set_monitor_slept_at(self, value):
        return self._db.set(self._MONITOR_SLEPT_AT, value.strftime(DATETIME_FORMAT) if value else value)

    def daily_status_sent(self, default=None, notify=False):
        value = self._db.get(self._DAILY_STATUS_SENT, notify=notify) or default
        return datetime.strptime(value, DATETIME_FORMAT) if value else value

    def set_daily_status_sent(self, value):
        return self._db.set(self._DAILY_STATUS_SENT, value.strftime(DATETIME_FORMAT) if value else value)

    def current_balance(self, default=0.0):
        return float(self._db.get(self._INITIAL_BALANCE) or default)

    def set_current_balance(self, value):
        return self._db.set(self._INITIAL_BALANCE, float(value))

    def last_reg_status(self, default="UNDEFINED"):
        return self._db.get(self._LAST_REG_STATUS) or default

    def set_last_reg_status(self, value):
        return self._db.set(self._LAST_REG_STATUS, value)


vs = Storage()
atexit.register(vs._db.close)
