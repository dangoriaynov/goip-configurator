#!/usr/bin/env python
# coding=utf-8
from src.const import IP, USER, PASS, SIP, SIP_PASS
from src.monitors import GoipMonitor, CallMonitor
from src.utils import safe


@safe(msg="Я впав та не можу піднятись. Поможіть!")
def main():
    goip = GoipMonitor(IP, USER, PASS, SIP, SIP_PASS)
    CallMonitor(goip).monitor()
    goip.send_greenting()


if __name__ == '__main__':
    main()
