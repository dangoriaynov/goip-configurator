#!/usr/bin/env python
# coding=utf-8
import html
import telegram
from telegram.parsemode import ParseMode
from telegram.utils.request import Request

from src.const import TEL_KEY, TEL_CHAT, IS_PROD


class CommonBot:
    from src.utils import log, safe
    _bot = None
    default_msg_params = {}
    msg_append = "" if IS_PROD else " (ТЕСТ)"

    def __init__(self, token=TEL_KEY, chat_id=TEL_CHAT):
        request = Request(con_pool_size=4+6)  # 4 - used by default threads, 6 - extra capacity == 10 (8 recommended)
        self._bot = telegram.Bot(token=token, request=request)
        self.default_msg_params = {"chat_id": chat_id}

    @safe()
    def send(self, text, escape=False):
        self.log.info("[Bot] Send message text: %s" % text)
        if escape:
            text = html.escape(text)
        msg = self._bot.send_message(text="%s%s" % (text, self.msg_append),
                                     parse_mode=ParseMode.HTML,
                                     **self.default_msg_params)
        self.log.info("[Bot] Send message result: %s" % msg)
        return msg

    @safe()
    def edit(self, msg, text):
        if not isinstance(msg, telegram.Message):
            raise Exception("Incorrect param type (expected telegram.Message): %s" % msg)
        self.log.info("[Bot] Edit message %s, new text: '%s'" % (msg, text))
        msg = self._bot.edit_message_text(message_id=msg.message_id,
                                          text="%s%s" % (text, self.msg_append),
                                          **self.default_msg_params)
        self.log.info("[Bot] Edit message result: %s" % msg)
        return msg


bot = CommonBot()
