#!/usr/bin/env python
# coding=utf-8
import atexit
import base64
import signal
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from src.const import DRIVER_EXECUTABLE, STORE_SCREENS
from src.utils import log


class NotLoggedIn(Exception):
    pass


class Browser:
    driver = None

    def __init__(self, url, uname, pwd):
        self.close()
        self.url = url
        self.uname = uname
        self.pwd = pwd
        upwd = '%s:%s' % (uname, pwd)
        auth = "Basic %s" % base64.b64encode(upwd.encode("utf-8")).decode("utf-8")
        log.info("[Browser] Authorization: %s" % auth)
        webdriver.DesiredCapabilities.PHANTOMJS["phantomjs.page.customHeaders.Authorization"] = auth
        self.driver = webdriver.PhantomJS(executable_path=DRIVER_EXECUTABLE)
        self.go(url)
        if not self.is_authorized():
            self.screenshot("not-logged-in", force=True)
            raise NotLoggedIn("User '%s' is not logged (pwd='%s')" % (uname, pwd))
        
    def close(self, err_log=False):
        if not self.driver:
            return
        log.info("[Browser] Close")
        try:
            self.driver.close()  # close the current page
            self.driver.service.process.send_signal(signal.SIGTERM)  # kill the specific phantomjs child proc
            self.driver.quit()  # quit the node proc
        except Exception as e:
            if err_log:
                log.error("[Browser] Close exception : {}".format(e))
        self.driver = None
    
    def go(self, url):
        log.info("[Browser] Open URL: %s" % url)
        self.driver.get(url)
    
    def open_menu(self, name):
        log.info("[Browser] Open menu '%s'" % name)
        self.by_xpath("//div[contains(@class, 'title') and text()='%s']" % name).click()
        self.screenshot("Menu-%s" % name)
        
    def by_xpath(self, xpath):
        return self.driver.find_element_by_xpath(xpath)
        
    def by_id(self, id):
        return self.driver.find_element_by_id(id)
    
    def set_text(self, elem, text):
        elem.clear()
        elem.send_keys(text)
        
    def set_select(self, id, value):
        self.by_xpath("//select[@id='%s']/option[text()='%s']" % (id, value)).click()
        
    def save(self):
        log.info("[Browser] Click [Save Changes] button")
        self.by_xpath("//input[@type='submit' and @value='Save Changes']").click()
        
    def expand_items(self, name):
        self.by_xpath("//div[contains(@style, 'cursor:hand') and text()='%s']" % name).click()
        
    def disable_codec(self, name):
        codec = self.by_xpath(
            "//div[@class='audiocodec' and span[@class='codec_name' and text()='%s']]/input[@type='checkbox']" % name)
        if codec.get_attribute("checked"):
            codec.click()
    
    def move_up_codec(self, name, times: int):
        self.by_xpath("//div[@class='audiocodec' and span[@class='codec_name' and text()='%s']]" % name)
        for i in range(1, times):
            self.by_xpath("//input[@type='button' and @value='UP']").click()
            
    def screenshot(self, name, force=False):
        if not STORE_SCREENS and not force:
            return
        self.driver.save_screenshot('%s.png' % name)
        
    def uptime_sec(self):
        value = self.driver.execute_script('return uptime_s')
        log.info("[Browser] Received uptime value '%s'" % value)
        return int(value)
    
    def current_url(self):
        return self.driver.current_url
    
    def go_relative_url(self, url):
        return self.go(self.current_url().rsplit("/", 1)[0] + "/" + url)

    def is_authorized(self):
        try:
            return self.by_xpath("//div[contains(@class, 'title') and text()='Status']").is_displayed()
        except NoSuchElementException:
            return False


class BrowserWrapper:
    b = None

    @classmethod
    def init(cls, url, uname, pwd):
        cls.kill()
        cls.b = Browser(url, uname, pwd)

    @classmethod
    def kill(cls):
        if cls.b:
            cls.b.close(err_log=False)
            cls.b = None


atexit.register(BrowserWrapper.kill)
