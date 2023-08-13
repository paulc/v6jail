#!/bin/sh

# Configure Linux jail
#
# To run:
#
# python3 -mv6jail.cli --base <linux_base> run --linux --fastboot --fastboot-cmd 'chroot /compat/ubuntu /usr/sbin/service ssh start' <name>
#

set -o pipefail
set -o errexit
set -o nounset

ZPATH=${ZPATH-zroot/jail}
TARGET=${1?Usage: $0 <base>}
LATEST_BASE=$(zfs list -t snap -Hr -s creation -o name zroot/jail/base | tail -1)

# Create volume
zfs send -c $LATEST_BASE | zfs recv -v ${ZPATH}/${TARGET}

python3 -mv6jail.cli --base ${TARGET} chroot-base --snapshot <<EOM

sysrc sshd_flags="-o AuthenticationMethods=publickey -o PermitRootLogin=prohibit-password -o Port=5022"

pkg install -y debootstrap
if debootstrap --no-check-gpg bionic /compat/ubuntu 
then
   echo debootstrap ok
else
   echo debootstrap error - carrying on
fi

echo "APT::Cache-Start 251658240;" | tee /compat/ubuntu/etc/apt/apt.conf.d/00aptitude

mkdir /home

tee /etc/fstab <<__FSTAB__
devfs           /compat/ubuntu/dev      devfs           rw,late                      0       0
tmpfs           /compat/ubuntu/dev/shm  tmpfs           rw,late,size=1g,mode=1777    0       0
fdescfs         /compat/ubuntu/dev/fd   fdescfs         rw,late,linrdlnk             0       0
linprocfs       /compat/ubuntu/proc     linprocfs       rw,late                      0       0
linsysfs        /compat/ubuntu/sys      linsysfs        rw,late                      0       0
/tmp            /compat/ubuntu/tmp      nullfs          rw,late                      0       0
/home           /compat/ubuntu/home     nullfs          rw,late                      0       0
__FSTAB__

mount -alv

chroot /compat/ubuntu /usr/bin/apt update
chroot /compat/ubuntu /usr/bin/apt install -y openssh-server || echo ERROR - Carrying On
chroot /compat/ubuntu /usr/bin/apt remove -y rsyslog || echo ERROR - Carrying On

umount -avf

EOM
