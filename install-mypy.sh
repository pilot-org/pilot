#!/bin/bash
sudo apt intsall python3.8-venv
python3.8 -m venv ~/.mypyls
~/.mypyls/bin/pip install "https://github.com/matangover/mypyls/archive/master.zip#egg=mypyls[default-mypy]"