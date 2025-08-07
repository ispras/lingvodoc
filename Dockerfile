FROM ubuntu:22.04
RUN apt-get update && apt-get install -y locales
RUN locale-gen ru_RU.UTF-8
ENV LANG='ru_RU.UTF-8' LANGUAGE='ru_RU:ru' LC_ALL='ru_RU.UTF-8' DEBIAN_FRONTEND=noninteractive
ADD . /api
WORKDIR /api

# Base apps and custom repository
RUN apt update && apt install -y wget gnupg2

# Modifying sources.list and app keys
RUN wget -O- https://packages.sil.org/keys/pso-keyring-2016.gpg > /etc/apt/trusted.gpg.d/pso-keyring-2016.gpg && \
    . /etc/os-release && echo "deb http://packages.sil.org/$ID $VERSION_CODENAME main" > /etc/apt/sources.list.d/packages-sil-org.list && \
    echo "deb http://apt.postgresql.org/pub/repos/apt/ $VERSION_CODENAME-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
	wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

# Most apps installing
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && apt install -y \
    python3.10 python3.10-dev python3.10-distutils \
    libssl-dev libffi-dev build-essential \
    xz-utils bzip2 tar unzip git \
    postgresql-server-dev-13 postgresql-client-13 libpq-dev \
    fonts-sil-gentium fonts-sil-gentium-basic fonts-sil-gentiumplus \
    fonts-sil-gentiumplus-compact libxft-dev \
    libpng16-16 libpng-dev libfreetype6 libfreetype6-dev \
    ffmpeg libxml2-dev libxslt-dev curl rsync mecab
    #libfreetype-dev

# Adjusting git and pip
RUN \
  git config --global http.postBuffer 500M && \
  git config --global http.maxRequestBuffer 100M && \
  git config --global core.compression 0 && \
  ln -sf $(which python3.10) /usr/bin/python3 && \
  ln -sf /etc/mecabrc /usr/local/etc/mecabrc && \
  curl -sS https://bootstrap.pypa.io/get-pip.py | python3.10 && \
  pip3 install pip==20.3.2 setuptools==44.0

# Installing python packages
RUN --mount=type=cache,target=/root/.cache/pip \
  pip3 install -r server-requirements-1.txt && \
  pip3 install -r server-requirements-final.txt

# Special steps for apertium parsers
RUN \
  locale-gen en_US.UTF-8 && update-locale && \
  ( curl -sS https://apertium.projectjj.com/apt/install-nightly.sh | bash ) && \
  apt install -y lttoolbox apertium-dev apertium-lex-tools apertium-separable hfst libhfst-dev cg3 cg3-dev autoconf

# Special steps for liboslon.so
RUN \
  wget https://github.com/ispras/lingvodoc-ext-oslon/archive/master.zip -O /tmp/master.zip && \
  unzip /tmp/master.zip -d /tmp/ && \
  g++ -O2 -fPIC -shared -Wl,-soname,liboslon.so -Wno-write-strings -o /usr/lib/liboslon.so /tmp/lingvodoc-ext-oslon-master/analysis.cpp && \
  ldconfig

# Some final steps
RUN \
  pip3 install setuptools==58.0
