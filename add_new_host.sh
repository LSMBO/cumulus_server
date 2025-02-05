# Copyright or © or Copr. Alexandre BUREL for LSMBO / IPHC UMR7178 / CNRS (2024)
# 
# [a.burel@unistra.fr]
# 
# This software is the server for Cumulus, a client-server to operate jobs on a Cloud.
# 
# This software is governed by the CeCILL license under French law and
# abiding by the rules of distribution of free software.  You can  use, 
# modify and/ or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info". 
# 
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability. 
# 
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or 
# data to be ensured and,  more generally, to use and operate it in the 
# same conditions as regards security. 
# 
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL license and that you accept its terms.

# This script will be sent to the new host and will be executed there
# For this script to work, we assume three things:
# - the system is Debian-based (it was tested on Ubuntu 22.04)
# - the system is up-to-date, especially the kernel (otherwise, apt install may require user input)
# - the user uses a certificate without password for authentication, so using sudo works without password

# get the user inputs
controller=$1
mountdir="$2"
# get the user login
user=`whoami`

# check that the mountdir is not already existing
if [[ ! -d $mountdir ]]
then
	# install required components (this may not work if the system is not up-to-date)
	sudo apt --yes install nfs-common libgomp1 mono-complete
	# create the directory that will be used as a mounting point
	sudo install -d -m 0755 -o $user -g $user $mountdir
	# update the fstab file
	cp /etc/fstab /tmp/cumulus.fstab.backup
	cmd="$controller:$mountdir $mountdir nfs rsize=8192,wsize=8192,timeo=14,intr"
	sudo sh -c "echo $cmd >> /etc/fstab"
	# mount the shared directory
	sudo mount $mountdir
	# gather information for the controller
	name=`hostname`
	echo "New host name: $name"
	cpu=`cat /proc/cpuinfo |grep -c processor`
	echo "Number of CPU: $cpu"
	ram=`grep MemTotal /proc/meminfo|sed 's/[^0-9]//g'`
	echo "Amount of RAM: $ram"
	# make sure that the folder for the pids is existing
	mkdir -p /storage/pids/
	# add a job to the crontab, to monitor the pids every minutes (so we don't have to connect all the time to check whether a pid is alive)
	crontab -l | echo "* * * * * /storage/utils/monitor_pids.sh" | crontab -
else
	# if mountdir exists, it can mean that the host has already been added
	# or that the directory is already used for something else
	echo "Error: Mount directory already exists!"
fi

