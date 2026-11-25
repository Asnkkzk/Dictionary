# -*- coding: utf-8 -*-
"""随取词典启动入口。双击或运行：python main.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from worddict.app import main

if __name__ == "__main__":
    main()
