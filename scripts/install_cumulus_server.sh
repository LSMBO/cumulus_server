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

# IMPORTANT: this is not an installation script, it is meant as a guide to help you setup a Cumulus server
# Cumulus has been developped for a Ubuntu 24.04 environment

# install dependencies
apt-get update
sudo apt --yes install python3-venv nfs-kernel-server libgomp1 mono-complete chrony docker.io dotnet8

# add user to the docker group (otherwise you need to call docker with sudo)
# this will only be effective after user logs out and logs in again
sudo usermod -aG docker ubuntu

# install openstack
sudo mkdir /usr/local/openstack_client
sudo chown ubuntu:ubuntu /usr/local/openstack_client
cd /usr/local/openstack_client
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install python-openstackclient

# configure openstack
mkdir -p ~/.config/openstack
touch 	~/.config/openstack/clouds.yaml
# the yaml file should look like this:
# clouds:
#   my-cloud:
#     auth:
#       auth_url: 'https://<your-openstack-server>:5000/v3'
#       project_name: '<project-name>'
#       project_domain_name: '<domain-name>'
#       username: '<username>'
#       user_domain_name: '<domain-name>'
#       password: '<user-password>'
#     region_name: '<region>'

# create the main folder
sudo mkdir /cumulus
sudo chown -R $user:$user /cumulus

# optional
## this directory should be on a large partition, if you have created a volume on openstack, you may have to format the volume (ie. create /etc/vdb1 from /etc/vdb)
# sudo parted /dev/vdb --script mklabel gpt
# sudo parted /dev/vdb --script mkpart primary ext4 0% 100%
# sudo mkfs.ext4 /dev/vdb1
## add the following line to /etc/fstab
# /dev/vdb1 /cumulus/data ext4 defaults 0 0
## mount the partition
# sudo mount -a

# create the required folders
mkdir /cumulus/bin # this folder will contain the scripts
mkdir /cumulus/data # this folder will be used to mount the data volume
mkdir /cumulus/temp # this folder will be used when converting files and to store temporary data
mkdir /cumulus/jobs # this folder will contain the job files

# retrieve the binaries
# TODO install git or github, authenticate if you want to push/pull
cd /cumulus/bin
gh repo clone LSMBO/cumulus_server
cd cumulus_server
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# share /cumulus with NFS
# TODO add the following line to /etc/exports (adjust the IP address)
# /cumulus 10.11.12.0/24(rw,async,no_subtree_check)
sudo systemctl restart nfs-kernel-server

# TODO create a template worker
# it's another VM that will be cloned for each job. We consider that this VM is based on a volume, with the OS installed on it.
# it's the volume that is cloned, not the VM itself
# you do not need a powerful VM for the template, but you should have enough space to manage a big job, and install all the required apps
# apps are installed directly on the template, docker images should also be stored there

# TODO make a snapshot of the template volume
# you will have to recreate the snapshot everytime you change something on the template (ie. add an app)

# TODO configure cumulus.conf and flavors.conf