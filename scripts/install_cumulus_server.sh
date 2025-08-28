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

#IMPORTANT: this script has NOT been tested yet, consider it more like a guide to install a Cumulus server

# arguments (TODO put all the arguments in a config file?)
openstack_config_file=$1 # Path for the openstack configuration file, ie. /home/user/.config/openstack/clouds.yaml
network_ip_range=$2 # IP range for the NFS share, ie. 172.16.0/24 or *
data_volume_size_gb=$3 # Size of the data volume in GB, ie. 10000
template_flavor=$4 # Flavor for the template server, ie. m1.large
template_image=$5 # Image for the template server, ie. ubuntu-22.04
template_volume_size_gb=$6 # Size of the template volume in GB, ie. 100 (there should be enough space for the OS, the apps, docker images, etc.)

# other variables
$hostname=`hostname`
$user=`whoami`

# install the dependencies
apt-get update
sudo apt --yes install python3-venv

# install openstack client
mkdir /usr/local/openstack_client
cd /usr/local/openstack_client
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install python-openstackclient
# copy the openstack config file where openstack client can find it
mkdir -p ~/.config/openstack
cp $openstack_config_file ~/.config/openstack/clouds.yaml
## copy the openstack config file and create a permanent environment variable in the bashrc file
# echo "export OS_CLIENT_CONFIG_FILE=/usr/local/openstack_client/clouds.yaml" >> /etc/bash.bashrc
# export OS_CLIENT_CONFIG_FILE=/usr/local/openstack_client/clouds.yaml

# create the whole environment for Cumulus
# mkdir /cumulus
# sudo chown -R $user:$user /cumulus
sudo install -d -m 0755 -o $user -g $user /cumulus # create the main directory, owner is the user
mkdir /cumulus/bin # this folder will contain the scripts
mkdir /cumulus/data # this folder will be used to mount the data volume
mkdir /cumulus/temp # this folder will be used when converting files and to store temporary data
mkdir /cumulus/jobs # this folder will be shared with NFS
mkdir /cumulus/jobs/__logs__
# use openstack to create a volume that will contain the data, this volume will be cloned for each job
openstack volume create --size $data_volume_size_gb --type ceph2 cumulus_data_volume
# attach the volume to the server and get the device name (ie. /dev/vdb)
device=$(openstack server add volume $hostname cumulus_data_volume | grep "attached to" | awk '{print $4}' | sed 's/.$//')
# format the volume, we want to create a /etc/vdb1 from /etc/vdb
sudo parted $device --script mklabel gpt
sudo parted $device --script mkpart primary ext4 0% 100%
partition="${device}1"
sudo mkfs.ext4 $partition
# add the mount to the fstab file so that it is mounted at boot
cmd="$partition /cumulus/data ext4 defaults 0 0"
sudo sh -c "echo $cmd >> /etc/fstab"
# mount the volume
sudo mount -a

# create a volume for the template server, it should be bootable on the given image
openstack volume create --size $template_volume_size_gb --image $template_image --type ceph2 --bootable cumulus_template_volume
# TODO wait for the volume to be available
# TODO check if the volume has to be formatted, it should be already formatted with the image

# create the template server with limited resources, based on the template volume
openstack server create --flavor $template_flavor --volume "cumulus_template_volume" "cumulus_template_server"
# TODO wait for the server to be available

# share the /cumulus/jobs folder with NFS
sudo apt --yes install nfs-kernel-server
echo "/cumulus/jobs $network_ip_range(rw,async,no_subtree_check)" >> /etc/exports
sudo systemctl restart nfs-kernel-server

# At this point, the server is ready to be used with Cumulus.
# The template server can be used to create new servers for each job. User has to mount the NFS share on the client side to access the jobs folder.
# It is the user's responsibility to secure the server, for example by installing a firewall, configuring SSH access, etc.


# # TODO get the paths from the config file
# # create the main directory
# mkdir -p /cumulus
# # create the folder where the Cumulus server will be installed
# mkdir /cumulus/bin
# # create a folder for the data that will be shared with NFS
# mkdir /cumulus/data
# # create a folder for the jobs that will not be shared
# mkdir /cumulus/jobs
# # create a folder for the temporary data related to the running jobs, that folder will be shared
# mkdir /cumulus/temp
# # create a folder where the template volume will be mounted
# mkdir /cumulus/template
# # create a folder where the temporary volumes will be mounted
# mkdir /cumulus/workspaces

# # install openstack client and create environment variables

# # share the folders with NFS

# # fetch from GitHub

# # copy the scripts that need to be called remotely to the temp folder
# cp /cumulus/bin/scripts/install_current_worker.sh /cumulus/temp/
# cp /cumulus/bin/scripts/start_job.sh /cumulus/temp/

# # configure files
# # create the service