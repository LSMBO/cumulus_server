import logging
import os
import paramiko
from shutil import rmtree
import time
import json

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
			name, address, user, port, rsa_key, cpu, ram = host.split("\t")
			HOSTS.append(Host(name, address, port, user, rsa_key, cpu, ram))
		f.close()
		# remove first item of the list, it's the header of the file
		HOSTS.pop(0)
	# return the list
	return HOSTS

def get_host(host_name):
	matches = list(filter(lambda host: host.name == host_name, get_all_hosts()))
	return None if len(matches) == 0 else matches[0]

def remote_exec(host, command):
	# connect to the host
	key = paramiko.RSAKey.from_private_key_file(host.rsa_key)
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	#ssh.connect(ip, port = port, username = user, pkey = key)
	ssh.connect(host.address, port = host.port, username = host.user, pkey = key)
	# execute the command remotely
	_, stdout, stderr = ssh.exec_command("echo $$ && exec " + command)
	pid = int(stdout.readline())
	# convert the outputs to text
	stdout = stdout.read().decode('ascii').strip("\n")
	stderr = stderr.read().decode('ascii').strip("\n")
	# close the connection and return outputs
	ssh.close()
	return pid, stdout, stderr

def write_file(file_path, content):
	f = open(file_path, "w")
	f.write(content + "\n")
	f.close()

def write_local_file(job_id, file_name, content):
	write_file(db.get_job_dir(job_id) + "/.cumulus." + file_name, content)

def create_job_directory(job_dir, form):
	#job_dir = get_job_dir(job_id)
	if not os.path.isfile(job_dir): os.mkdir(job_dir)
	# add a .cumulus.settings file with basic information from the database, to make it easier to find proprer folder
	write_file(job_dir + "/.cumulus.settings", json.dumps(form))

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
	if os.path.isdir(job_dir):
		# list all files including sub-directories
		root_path = job_dir + "/"
		for root, dirs, files in os.walk(root_path):
			# make sure that the file pathes are relative to the root of the job folder
			rel_path = root.replace(root_path, "")
			for f in files:
				# avoid the .cumulus.* files and .RSYNC_OK file
				if f != config.get("final.file") and not f.startswith(".cumulus."):
					# return an array of tuples (name|size)
					file = f if rel_path == "" else rel_path + "/" + f
					filelist.append((file, get_size(root_path + "/" + file)))
	# the user will select the files they want to retrieve
	return filelist

def delete_raw_file(file):
	try:
		if os.path.isfile(file): os.remove(file)
		else: rmtree(file)
	except OSError as o:
		logger.error(f"Can't delete raw file {file}: {o.strerror}")

def delete_job_folder(job_id):
	try:
		job_dir = db.get_job_dir(job_id)
		if os.path.isdir(job_dir): 
			rmtree(job_dir)
			logger.info(f"Job folder '{job_dir}' has been deleted")
		return True
	except OSError as o:
		db.set_status(job_id, "FAILED")
		logger.error(f"Can't delete job folder for {db.get_job_to_string(job_id)}: {o.strerror}")
		db.add_to_stderr(job_id, f"Can't delete job folder for {db.get_job_to_string(job_id)}: {o.strerror}")
		return False

def cancel_job(job_id):
	# get the pid and the host
	pid = db.get_pid(job_id)
	host_name = db.get_host(job_id)
	# use ssh to kill the pid (may not be needed if the job is still pending)
	# FIXME transform the host_name to host
	host = get_host(host_name)
	if pid is not None and pid > 0: remote_exec(host, f"kill -9 {pid}")
	# change the status
	db.set_status(job_id, "CANCELLED")
	db.set_pid(job_id, None)
	# delete the job directory
	return delete_job_folder(job_id)

def get_stdout_file_name(app_name): return f".{app_name}.stdout"
def get_stderr_file_name(app_name): return f".{app_name}.stderr"

def get_file_age_in_days(file):
	# mtime is the date in seconds since epoch since the last modification
	# time() is the current time
	# divide by the number of seconds in a day to have the number of days
	if file is None: return 0
	return (time.time() - os.path.getmtime(file)) / 86400

def get_version(): return config.get("version")
