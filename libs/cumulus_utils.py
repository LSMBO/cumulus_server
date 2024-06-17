import logging
import os
import paramiko
import shutils
import time

import cumulus_server.libs.cumulus_config as config
import cumulus_server.libs.cumulus_database as db

logger = logging.getLogger(__name__)

DATA_DIR = config.get("storage.data.path")
JOB_DIR = config.get("storage.jobs.path")
HOSTS = []

class Host:
	# TODO maybe add a max number of jobs per host?
	def __init__(self, name, address, port, user, rsa_key, cpu, ram):
		self.name = name
		self.address = address
		self.port = port
		self.user = user
		self.rsa_key = rsa_key
		self.cpu = cpu
		self.ram = ram
	def __str__(self):
		return f"{self.name}\t{self.address}\t{self.port}\t{self.user}\t{self.cpu}\t{self.ram}"
	def to_dict(self):
		runnings, pendings = db.get_alive_jobs_per_host(self.name)
		return {"name": self.name, "cpu": self.cpu, "ram": self.ram, "jobs_running": runnings, "jobs_pending": pendings}

def get_all_hosts(reload_list = False):
	# the hosts are stored in a global array
	if len(HOSTS) == 0 or reload_list:
		# reload_list is True when a client asks for the list
		HOSTS.clear()
		# get the list of hosts from the file
		f = open(config.get("hosts.file.path"), "r")
		for host in f.read().strip("\n").split("\n"):
			name, address, port, user, rsa_key, cpu, ram = host.split("\t")
			HOSTS.append(Host(name, address, port, user, rsa_key, cpu, ram))
		f.close()
		# remove first item of the list, it's the header of the file
		HOSTS.pop(0)
	# return the list
	return HOSTS

#def get_all_hosts():
#  # TODO do not read the file everytime (but it would be nice to be able to add hosts without restarting the server)
#  hosts = []
#  # get the list of hosts from the file
#  #f = open(HOST_FILE, "r")
#  f = open(config.get("hosts.file.path"), "r")
#  for host in f.read().strip("\n").split("\n"):
#    # TODO does it send an array as the first argument?
#    #hosts.append(Host(host.split("\t")))
#    name, address, port, user, rsa_key, cpu, ram = host.split("\t")
#    hosts.append(Host(name, address, port, user, rsa_key, cpu, ram))
#  f.close()
#  # remove first item of the list, it's the header of the file
#  hosts.pop(0)
#  # return the list
#  return hosts

def get_credentials(ip):
	# open the file to search for the ip and return the match
	for host in get_all_hosts():
		if host.address == ip: return host.user, host.rsa, host.port
	# return empty values if there is no host with that ip address
	return "", "", 0

def remote_exec(ip, command):
	# get the credentials
	user, key, port = get_credentials(ip)
	# connect to the host
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	ssh.connect(ip, port = port, username = user, pkey = key)
	# execute the command remotely
	_, stdout, stderr = ssh.exec_command("echo $$ && exec " + command)
	pid = int(stdout.readline())
	# convert the outputs to text
	stdout = stdout.read().decode('ascii').strip("\n")
	stderr = stderr.read().decode('ascii').strip("\n")
	# close the connection and return outputs
	ssh.close()
	return pid, stdout, stderr

#def get_job_dir(job_id):
#  return JOB_DIR + "/" + str(job_id)

def write_file(file_path, content):
	f = open(file_path, "w")
	f.write(content)
	f.close()

def write_local_file(job_id, file_name, content):
	write_file(db.get_job_dir(job_id) + "/.cumulus." + file_name, content)

#def create_job_directory(job_id):
def create_job_directory(job_dir, form):
	# add a .cumulus.settings file with basic information from the database, to make it easier to find proprer folder
	write_file(job_dir + "/.cumulus.settings", str(form))
	#job_dir = get_job_dir(job_id)
	if not os.path.isfile(job_dir): os.mkdir(job_dir)

def get_size(file):
	if os.path.isfile(file):
		return os.path.getsize(file)
	else:
		total_size = 0
		for dirpath, dirnames, filenames in os.walk(file):
			for f in filenames:
				fp = os.path.join(dirpath, f)
				# skip if it is symbolic link
				if not os.path.islink(fp): total_size += os.path.getsize(fp)
		return total_size

def get_raw_file_list():
	filelist = []
	for file in os.listdir(DATA_DIR):
		filelist.append((file, get_size(DATA_DIR + "/" + file)))
	return filelist

def get_file_list(job_id):
	filelist = []
	job_dir = db.get_job_dir(job_id)
	if os.path.isfile(job_dir):
		# list all files including sub-directories
		root_path = job_dir + "/"
		for root, dirs, files in os.walk(root_path):
			# make sure that the file pathes are relative to the root of the job folder
			rel_path = root.replace(root_path, "")
			for f in files:
				# avoid the .cumulus.* files
				if not f.startswith(".cumulus."):
					# return an array of tuples (name|size)
					file = f if rel_path == "" else rel_path + "/" + f
					filelist.append((file, get_size(file)))
	# the user will select the files they want to retrieve
	return filelist

def delete_raw_file(file):
	try:
		if os.path.isfile(file): os.remove(file)
		else: shutils.rmtree(file)
	except OSError as o:
		logger.error(f"Can't delete raw file {file}: {o.strerror}")

def delete_job_folder(job_id):
	try:
		shutils.rmtree(db.get_job_dir(job_id))
		return true
	except OSError as o:
		db.set_status(job_id, "FAILED")
		logger.error(f"Can't delete job folder for {db.get_job_to_string(job_id)}: {o.strerror}")
		db.add_to_stderr(job_id, f"Can't delete job folder for {db.get_job_to_string(job_id)}: {o.strerror}")
		return false

def cancel_job(job_id):
	# get the pid and the host
	pid = db.get_pid(job_id)
	host = db.get_host(job_id)
	# use ssh to kill the pid
	remote_exec(host, f"kill -9 {pid}")
	# delete the job directory
	return delete_job_folder(job_id)

def get_stdout_file_name(app_name): return f".{app_name}.stdout"
def get_stderr_file_name(app_name): return f".{app_name}.stderr"

def get_file_age_in_days(file):
	# mtime is the date in seconds since epoch since the last modification
	# time() is the current time
	# divide by the number of seconds in a day to have the number of days
	return (time.time() - os.path.getmtime(file)) / 86400

def get_version(): return config.get("version")
