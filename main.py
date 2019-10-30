#!/usr/bin/env python
# coding=utf-8
from src.const import IP, USER, PASS, SIP, SIP_PASS
from src.monitors import GoipMonitor
from src.utils import safe


@safe(msg="Я впав та не можу піднятись. Поможіть!")
def main():
    GoipMonitor(IP, USER, PASS, SIP, SIP_PASS)


if __name__ == '__main__':
    main()
