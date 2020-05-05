#!/usr/bin/env python
# coding=utf-8
from src.const import IP, USER, PASS, SIP, SIP_PASS
from src.monitors import GoipMonitor, CallMonitor
from src.utils import safe


@safe(msg="Я впав та не можу піднятись. Поможіть!")
def main():
    goip = GoipMonitor(IP, USER, PASS, SIP, SIP_PASS)
    cm = CallMonitor(goip)
    goip.send_greenting()
    cm.monitor()


if __name__ == '__main__':
    main()
