FROM python:3

# NOTE use lsmod and modprobe to ensure module is loaded in the host kernel
# module should exist in /lib/modules/.../nbd.ko
#
# Unload nbd module (sudo rmmod nbd)
#
# Run container --privileged -v /lib/modules:/lib/modules -v /dev:/dev and run inside:
#   modprobe nbd
#   nbd-server 2000 /export/blkdev
#   nbd-client localhost 2000 /dev/nbd0 -nonetlink
#   mkfs.ext4 /dev/ndb1 # Create the ext4 super blocks on this device
#   mkdir /mnt/mydir
#   mount -t ext4 -o norecovery /dev/nbd0 /mnt/mydir
#   disconnect with nbd-client -disconnect /dev/nbd0 -nonetlink
RUN apt-get update && apt-get install -y vim kmod nbd-server nbd-client

RUN pip3 install PySyncObj jaeger-client

RUN mkdir /export && touch /export/blkdev && dd if=/dev/zero of=/export/blkdev bs=1k count=500

RUN apt-get install -y postgresql postgresql-contrib sudo hdparm && \
    mkdir /mnt/pg && chown postgres /mnt/pg

ADD nbd/nbd.conf /etc/nbd-server/config
ADD nbd/nbd_allow.conf /etc/nbd-server/allow

RUN touch /tmp/blocks

ENV PYTHONPATH=/py
RUN mkdir /py/
ADD nbd /py/nbd

ENTRYPOINT ["python3", "-m", "nbd.server"]
