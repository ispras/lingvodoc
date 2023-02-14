FROM ubuntu:20.04
RUN apt-get update && apt-get install -y locales
RUN locale-gen ru_RU.UTF-8
ENV LANG='ru_RU.UTF-8' LANGUAGE='ru_RU:ru' LC_ALL='ru_RU.UTF-8' DEBIAN_FRONTEND=noninteractive
ADD . /api
WORKDIR /api
RUN apt update && apt install -y wget curl gnupg2 software-properties-common
RUN wget -O- https://packages.sil.org/keys/pso-keyring-2016.gpg > /etc/apt/trusted.gpg.d/pso-keyring-2016.gpg && \
    . /etc/os-release && echo "deb http://packages.sil.org/$ID $VERSION_CODENAME main" > /etc/apt/sources.list.d/packages-sil-org.list && \
    echo "deb http://apt.postgresql.org/pub/repos/apt/ focal-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
	wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
	apt-key add -
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get update && apt install -y python3.10-dev python3.10-distutils python3-setuptools \
    libssl-dev libffi-dev wget build-essential \
    xz-utils bzip2 tar unzip git \
    libpng16-16 libpng-dev libfreetype6 libfreetype-dev unzip \
    postgresql-server-dev-13 postgresql-client-13 libpq-dev \
    fonts-sil-gentium fonts-sil-gentium-basic fonts-sil-gentiumplus \
    fonts-sil-gentiumplus-compact libfreetype6-dev libxft-dev \
    ffmpeg libxml2-dev libxslt-dev
RUN \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.10 && \
    ln -sf $(which python3.10) $(which python3) && \
    ln -sf $(which pip3.10) /usr/local/bin/pip3
RUN \
  wget https://github.com/ispras/lingvodoc-ext-oslon/archive/master.zip -O /tmp/master.zip && \
  unzip /tmp/master.zip -d /tmp/ && \
  g++ -O2 -fPIC -shared -Wl,-soname,liboslon.so -Wno-write-strings -o /usr/lib/liboslon.so /tmp/lingvodoc-ext-oslon-master/analysis.cpp && \
  ldconfig
RUN \
  pip3 install -r server-requirements-1.txt && \
  pip3 install -r server-requirements-final.txt
RUN \
  locale-gen en_US.UTF-8 && update-locale && \
  ( curl -sS https://apertium.projectjj.com/apt/install-nightly.sh | bash ) && \
  apt install -y lttoolbox apertium-dev apertium-lex-tools apertium-separable hfst libhfst-dev cg3 cg3-dev autoconf
