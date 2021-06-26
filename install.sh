#!/bin/bash

install-apt-repository() {
	apt update && \
		apt install -y software-properties-common
}

install-tools() {
    install-apt-repository

	add-apt-repository ppa:rmescandon/yq -y
	apt update && \
		apt install -y expect yq jq
}

install-python-library() {
	python3.8 -m pip install -r requirements.txt
}

install-python() {
    install-apt-repository

	add-apt-repository ppa:deadsnakes/ppa -y # for python3.8
	apt update && \
		apt install -y python3.8 curl python3.8-distutils python3-apt
	curl https://bootstrap.pypa.io/get-pip.py | python3.8
	python3.8 -m pip install pipenv
}

install-python-dev() {
    install-apt-repository
    install-python

	pipenv install --dev
	pipenv run python setup.py develop
}

install-mypy() {
    install-python-dev

    pipenv install "https://github.com/matangover/mypyls/archive/master.zip#egg=mypyls[default-mypy]"
}

show-rc-install() {
    if [ "$1" = "--human" ]; then
	    echo "\033[1;33mPlease add following lines into your rc file (e.g. ~/.bashrc or ~/.zshrc)\033[0m"
    fi
	echo "PATH=\"\044{PATH}:$(shell pipenv --venv)/bin\""
	echo "eval \"\044(_SSSCLICK_COMPLETE=source_zsh sssclick)\""
	echo "alias assh=\"bash $(shell realpath .)/assh/assh.sh\""
}

all() {
    install-python-dev
    install-tools
    show-rc-install --human
}

if type "$1" > /dev/null; then
    cmd="$1"
    shift 1
    eval "${cmd}" "$@"
else
    >&2 echo "Known command: $1"
fi