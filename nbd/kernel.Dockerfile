FROM ubuntu

RUN apt-get update
RUN apt-get install -y linux-headers-5.4.0-39-generic linux-source-5.4
RUN apt-get install -y bc bison flex kmod libelf-dev libssl-dev

WORKDIR /usr/src/linux-source-5.4.0

RUN tar -xjvf linux-source-5.4.0.tar.bz2

WORKDIR /usr/src/linux-source-5.4.0/linux-source-5.4.0
RUN bash -c 'yes "" | make oldconfig'
RUN bash -c 'echo CONFIG_BLK_DEV_NBD=y >> .config'
RUN make prepare modules_prepare
RUN make drivers/block/nbd.ko
