#!/usr/bin/env python
# coding=utf-8
import threading
from collections import namedtuple
from functools import wraps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ChatAction
from telegram.ext import Updater, CommandHandler, PicklePersistence, CallbackQueryHandler, ConversationHandler, \
    Filters, MessageHandler

from src.bot.common import bot
from src.const import ALLOWED_USERS
from src.utils import log, sleep

FIX, BALANCE, REBOOT, USSD, SMS = range(5)

mm_choices = namedtuple("mm_choices", ['BALANCE', 'REBOOT_CONFIRM', 'FIX_CONFIRM', 'SMS_NUM', 'USSD_NUM'])
mm_labels = ['Баланс', 'Перевантаж', 'Полагодити', 'СМС', 'USSD']
mm_buttons = mm_choices(*mm_labels)

more_choices = namedtuple("more_choices", ['SEND_USSD', 'SMS_TEXT', 'SEND_SMS'])
more_labels = ['Слати USSD', 'Текст СМС', 'Слати СМС']
more_buttons = more_choices(*more_labels)

g_choices = namedtuple("g_choices", ['Cancel', 'StartOver', 'No', 'Yes'])
g_labels = ['Скасувати', 'Старт', 'Ні', 'Так']
g_buttons = g_choices(*g_labels)


def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu


def send_bot_msg(update, context, msg, reply_markup=None, noedit=False):
    if noedit and update.message:
        update.message.reply_text(text=msg, reply_markup=reply_markup)
        return
    if update.callback_query:
        update.callback_query.edit_message_text(text=msg, reply_markup=reply_markup)
    elif update.message:
        update.message.reply_text(text=msg, reply_markup=reply_markup)
    else:
        log.error("[Personal bot] Unable to send the message: %s" % msg)


def send_action(action=ChatAction.TYPING):
    """Sends `action` while processing func command."""
    def decorator(func):
        @wraps(func)
        def command_func(update, context, *args, **kwargs):
            context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=action)
            return func(update, context, *args, **kwargs)
        return command_func
    return decorator


def answer_query():
    """Answers callback query if any."""
    def decorator(func):
        @wraps(func)
        def command_func(update, context, *args, **kwargs):
            if update.callback_query:
                query = update.callback_query
                query.answer()
            return func(update, context, *args, **kwargs)
        return command_func
    return decorator


def restricted():
    """Restrict usage of func to allowed users only and replies if necessary."""
    def decorator(func):
        @wraps(func)
        def command_func(update, context, *args, **kwargs):
            if update is None or context is None:
                return func(update, context, *args, **kwargs)
            username = update.effective_user.username
            if username not in ALLOWED_USERS:
                log.error("[Personal bot] Unauthorized access denied for {}.".format(username))
                send_bot_msg(update, context, msg='Unauthorised.')
                return  # quit function
            return func(update, context, *args, **kwargs)
        return command_func
    return decorator


class BaseRequest:
    update = None
    context = None

    def __init__(self, update, context):
        self.update = update
        self.context = context
        send_bot_msg(update, context, msg="Створено запит")

    def process(self, *args, **kwargs):
        raise NotImplementedError("This method should be implemented")


class BalanceRequest(BaseRequest):
    def __init__(self, update, context):
        super().__init__(update, context)
        log.info("[Personal bot] Balance info requested")

    def process(self, *args, **kwargs):
        from src.monitors import daily_status
        return daily_status(scheduled_run=False)


class RebootRequest(BaseRequest):
    def __init__(self, update, context):
        super().__init__(update, context)
        log.info("[Personal bot] Reboot requested")

    def process(self, goip):
        return goip.reboot()


class ResetRestoreRequest(BaseRequest):
    def __init__(self, update, context):
        super().__init__(update, context)
        log.info("[Personal bot] Fix requested")

    def process(self, goip):
        return goip.fix()


class SendSmsRequest(BaseRequest):
    def __init__(self, update, context, num, text):
        super().__init__(update, context)
        self.num = num
        self.text = text
        log.info("[Personal bot] Send SMS requested: number=%s, message=%s" % (num, text))

    def process(self, *args, **kwargs):
        from src.sms import SmsWrapper
        return SmsWrapper.sms.send_sms(self.num, self.text)


class SendUssdRequest(BaseRequest):
    def __init__(self, update, context, code):
        super().__init__(update, context)
        self.code = code
        log.info("[Personal bot] Send USSD requested: code=%s" % code)

    def process(self, *args, **kwargs):
        from src.sms import SmsWrapper
        return SmsWrapper.sms.send_ussd(self.code, bot_msg=True)


def show_cancel_button(update, context, msg, cb_data):
    button_list = [
        InlineKeyboardButton(g_buttons.Cancel, callback_data=cb_data),
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1))
    send_bot_msg(update, context, msg=msg, reply_markup=reply_markup)


def show_confirm_buttons(update, context, msg):
    button_list = [
        InlineKeyboardButton(g_buttons.Cancel, callback_data=g_buttons.Cancel),
        InlineKeyboardButton(g_buttons.Yes, callback_data=g_buttons.Yes),
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=2))
    send_bot_msg(update, context, msg=msg, reply_markup=reply_markup)


def get_cnxt_val(context, key='choice'):
    user_data = context.user_data
    if key not in user_data:
        return
    value = user_data[key]
    del user_data[key]
    return value


def store_cnxt_val(context, key, value):
    user_data = context.user_data
    user_data[key] = value


@restricted()
@answer_query()
def start(update, context, first_run=True):
    # prevent someone from sending new requests while current one is still processed
    while pbot.has_request():
        context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
        log.info("[Personal bot] Waiting for request to be processed...")
        sleep(5)
    msg = 'Чим я можу допомогти?' if first_run else 'Може ще щось?'
    header_buttons = InlineKeyboardButton(mm_buttons.BALANCE, callback_data=mm_buttons.BALANCE)
    button_list = [
        InlineKeyboardButton(mm_buttons.REBOOT_CONFIRM, callback_data=mm_buttons.REBOOT_CONFIRM),
        InlineKeyboardButton(mm_buttons.FIX_CONFIRM, callback_data=mm_buttons.FIX_CONFIRM),
        InlineKeyboardButton(mm_buttons.SMS_NUM, callback_data=mm_buttons.SMS_NUM),
        InlineKeyboardButton(mm_buttons.USSD_NUM, callback_data=mm_buttons.USSD_NUM)
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=2, header_buttons=header_buttons))
    send_bot_msg(update, context, msg=msg, reply_markup=reply_markup, noedit=True)


@restricted()
def start_over(update, context):
    start(update, context, first_run=False)


@restricted()
def error(update, context):
    """Log Errors caused by Updates."""
    log.warning('[Personal bot] Update "%s" caused error "%s"', update, context.error)


@restricted()
@answer_query()
def balance(update, context):
    pbot.request = BalanceRequest(update, context)
    return g_buttons.StartOver


@restricted()
@answer_query()
def reboot_confirm(update, context):
    show_confirm_buttons(update, context, msg="Точно перевантажити?")
    return g_buttons.Yes


@restricted()
@answer_query()
def reboot(update, context):
    pbot.request = RebootRequest(update, context)
    return g_buttons.StartOver


@restricted()
@answer_query()
def fix_confirm(update, context):
    show_confirm_buttons(update, context, msg="Точно лагодити?")
    return g_buttons.Yes


@restricted()
@answer_query()
def fix(update, context):
    pbot.request = ResetRestoreRequest(update, context)
    return g_buttons.StartOver


@restricted()
@answer_query()
@send_action()
def ask_ussd_code(update, context):
    show_cancel_button(update, context, msg="Введи USSD код:", cb_data=g_buttons.Cancel)
    return more_buttons.SEND_USSD


@restricted()
def send_ussd(update, context):
    code = update.message.text
    pbot.request = SendUssdRequest(update, context, code=code)
    return g_buttons.StartOver


@restricted()
@answer_query()
@send_action()
def ask_sms_num(update, context):
    show_cancel_button(update, context, msg="Введи номер:", cb_data=g_buttons.Cancel)
    return more_buttons.SMS_TEXT


@restricted()
@send_action()
def ask_sms_text(update, context):
    num = update.message.text
    store_cnxt_val(context, "num", num)

    show_cancel_button(update, context, msg="Введи текст:", cb_data=g_buttons.Cancel)
    return more_buttons.SEND_SMS


@restricted()
def send_sms(update, context):
    num = get_cnxt_val(context, "num")
    text = update.message.text
    pbot.request = SendSmsRequest(update, context, num=num, text=text)
    return g_buttons.StartOver


class PersonalBot:
    request = None

    def __init__(self):
        persistence = PicklePersistence(filename='bot-settings')
        updater = Updater(bot=bot._bot, persistence=persistence, use_context=True)
        cancel_handler = CallbackQueryHandler(pattern='^%s$' % g_buttons.Cancel, callback=start)
        updater.dispatcher.add_handler(CommandHandler(command='start', callback=start))
        updater.dispatcher.add_handler(CallbackQueryHandler(pattern='^%s|%s$' % (g_buttons.Cancel, g_buttons.StartOver),
                                                            callback=start_over))
        updater.dispatcher.add_handler(CallbackQueryHandler(pattern='^%s$' % mm_buttons.BALANCE, callback=balance))
        reboot_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(pattern='^%s$' % mm_buttons.REBOOT_CONFIRM, callback=reboot_confirm)],
            states={
                g_buttons.Yes: [CallbackQueryHandler(pattern='^%s$' % g_buttons.Yes, callback=reboot)],
            },
            allow_reentry=True, per_message=False, fallbacks=[cancel_handler],
            name='reboot-handler'
        )
        updater.dispatcher.add_handler(reboot_conv_handler)
        fix_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(pattern='^%s$' % mm_buttons.FIX_CONFIRM, callback=fix_confirm)],
            states={
                g_buttons.Yes: [CallbackQueryHandler(pattern='^%s$' % g_buttons.Yes, callback=fix)],
            },
            allow_reentry=True, per_message=False, fallbacks=[cancel_handler],
            name='fix-handler'
        )
        updater.dispatcher.add_handler(fix_conv_handler)
        ussd_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(pattern='^%s$' % mm_buttons.USSD_NUM, callback=ask_ussd_code)],
            states={
                more_buttons.SEND_USSD: [MessageHandler(Filters.text, callback=send_ussd)],
            },
            allow_reentry=True, per_message=False, fallbacks=[cancel_handler],
            name='ussd-handler'
        )
        updater.dispatcher.add_handler(ussd_conv_handler)
        sms_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(pattern='^%s$' % mm_buttons.SMS_NUM, callback=ask_sms_num)],
            states={
                more_buttons.SMS_TEXT: [MessageHandler(Filters.text, callback=ask_sms_text)],
                more_buttons.SEND_SMS: [MessageHandler(Filters.text, callback=send_sms)],
            },
            allow_reentry=True, per_message=False, fallbacks=[cancel_handler],
            name='sms-handler'
        )
        updater.dispatcher.add_handler(sms_conv_handler)
        updater.dispatcher.add_error_handler(error)
        updater.start_polling()
        log.info("[Personal bot] Started")

    def has_request(self):
        return self.request is not None

    def process_request(self, goip):
        if not self.has_request():
            log.info("[ProcessRequest] No request to process")
            return
        update = self.request.update
        context = self.request.context
        try:
            threading.Thread(target=start_over, args=(update, context, )).start()
            send_bot_msg(update, context, msg="Виконую запит")
            result = self.request.process(goip)
            if result:
                bot.send(result)
            send_bot_msg(update, context, msg="Тринь, ісполнєно!")
        except Exception as e:
            try:
                send_bot_msg(update, context, msg="Трапилась помилка")
                log.error("[Personal bot] Exception while processing request: %s" % e)
            except Exception as e1:
                log.error("[Personal bot] Exception while handling exception: %s\noriginal exception: %s" % (e1, e))
        finally:
            self.request = None


pbot = PersonalBot()
