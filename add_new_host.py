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

import os
import math
import paramiko
import re
import subprocess
import sys

# get the arguments
address = sys.argv[1]
user = sys.argv[2] # default should be ubuntu
port = sys.argv[3] # default should be 22
rsa_file = sys.argv[4] # default should be ~/.ssh/cumulus.pem

# ssh connection
ssh = paramiko.SSHClient()
ssh.get_host_keys().add(address, 'ssh-rsa', paramiko.RSAKey.from_private_key_file(rsa_file))

def read_config():
	storage = ""
	hosts_file = ""
	local_ip = subprocess.run(['hostname', '-I'], capture_output=True, text=True).stdout.strip()
	f = open(os.path.abspath("cumulus.conf"), "r")
	for line in f.read().strip("\n").split("\n"):
		line = re.sub(r"\s*\t*#.*", "", line.replace("//", "#"))
		if "=" in line:
			key, value = line.split("=")
			if key.strip() == "storage.path": storage = value.strip()
			elif key.strip() == "hosts.file.path": hosts_file = value.strip()
	f.close()
	return storage, hosts_file, local_ip

def get_local_ip_address():
	return subprocess.run(['hostname', '-I'], capture_output=True, text=True).stdout.strip()

def is_connected():
	global ssh
	transport = ssh.get_transport() if ssh else None
	return transport and transport.is_active()

def connection():
	global ssh
	if not is_connected():
		ssh = paramiko.SSHClient()
		ssh.load_system_host_keys()
		#ssh.connect(address, port, username = user, key_filename = rsa_file)
		ssh.connect(address, username = user, key_filename = rsa_file)

def run_command(command):
	global ssh
	connection()
	return ssh.exec_command(command)

def send_file(local_file, remote_file):
	global ssh
	connection()
	sftp = ssh.open_sftp()
	sftp.put(os.path.abspath(local_file), remote_file)
	sftp.close()

def read_stdout(stdout):
	name = ""
	cpu = 0
	ram = 0
	for line in stdout:
		if line.startswith("New host name: "): name = line.split(": ")[1].strip()
		elif line.startswith("Number of CPU: "): cpu = line.split(": ")[1].strip()
		elif line.startswith("Amount of RAM: "): ram = math.floor(int(line.split(": ")[1].strip()) / 1024000)
		elif line.startswith("Error: "): name = name = line.strip()
	return name, cpu, ram

def main():
	try:
		# get local information
		storage, hosts_file, local_ip = read_config()
		# send the script to the new host
		script = "add_new_host.sh"
		remote_script = f"/tmp/{script}"
		send_file(script, remote_script)
		# execute the script remotely
		stdin, stdout, stderr = run_command(f"source {remote_script} {local_ip} {storage}")
		# extract values from stdout
		name, cpu, ram = read_stdout(stdout)
		# deal with eventual errors
		if name.startswith("Error"):
			print(f"{name}\nPlease fix this manually.")
		else:
			# add values in the hosts file
			#print(f"Adding to '{hosts_file}': {name}\t{address}\t{user}\t{port}\t{rsa_file}\t{cpu}\t{ram}")
			with open(hosts_file, "a") as hosts:
				hosts.write(f"{name}\t{address}\t{user}\t{port}\t{rsa_file}\t{cpu}\t{ram}\n")
			print("All done.")
	except ValueError as ve:
		return str(ve)

if __name__ == "__main__":
	sys.exit(main())

