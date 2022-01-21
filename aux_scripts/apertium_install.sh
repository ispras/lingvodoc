#!/bin/bash
if [ $# -eq 0 ]; then
    echo -e "Needs one parameter: the path to the directory where apertium packages should be installed ";
    exit 1;
fi;
if ! [ -d "$1" ]; then
    echo -e "Passed parameter is not a valid path. ";
    exit 1;
fi;
locale-gen en_US.UTF-8 && update-locale;
apt install -y lttoolbox apertium-dev \
apertium-lex-tools hfst libhfst-dev cg3 cg3-dev autoconf;
if ! [ -d "$1/apertium-kaz" ]; then git clone https://github.com/apertium/apertium-kaz $1/apertium-kaz; fi;
cd $1/apertium-kaz && ./autogen.sh && ./configure && make && make install;
if ! [ -d "$1/apertium-tat" ]; then git clone https://github.com/apertium/apertium-tat $1/apertium-tat; fi;
cd $1/apertium-tat && ./autogen.sh && ./configure && make && make install;
if ! [ -d "$1/apertium-rus" ]; then git clone https://github.com/apertium/apertium-rus $1/apertium-rus; fi;
cd $1/apertium-rus && ./autogen.sh && ./configure && make && make install;
if ! [ -d "$1/apertium-kaz-rus" ]; then git clone https://github.com/apertium/apertium-kaz-rus $1/apertium-kaz-rus; fi;
cd $1/apertium-kaz-rus && ./autogen.sh && ./configure && make && make install;
if ! [ -d "$1/apertium-tat-rus" ]; then git clone https://github.com/apertium/apertium-tat-rus $1/apertium-tat-rus; fi;
cd $1/apertium-tat-rus && ./autogen.sh && ./configure && make && make install;
if ! [ -d "$1/apertium-sah" ]; then git clone https://github.com/apertium/apertium-sah $1/apertium-sah; fi;
cd $1/apertium-sah && ./autogen.sh && ./configure && make && make install;
