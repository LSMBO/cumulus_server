# Copyright or © or Copr. Alexandre BUREL for LSMBO / IPHC UMR7178 / CNRS (2025)
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

import json
import logging
import os
import paramiko
import re
import shutil
import time

import libs.cumulus_config as config
import libs.cumulus_database as db

logger = logging.getLogger(__name__)
HOSTS = []

class Host:
	# TODO maybe add a max number of jobs per host?
	def __init__(self, name, address, port, user, rsa_key, cpu, ram):
		self.name = name
		self.address = address
		self.port = port
		self.user = user
		self.rsa_key = rsa_key
		self.cpu = int(cpu)
		self.ram = int(ram)
	def __str__(self):
		return f"{self.name}\t{self.address}\t{self.port}\t{self.user}\t{self.cpu}\t{self.ram}"
	def to_dict(self):
		pendings, runnings = db.get_alive_jobs_per_host(self.name)
		return {"name": self.name, "cpu": self.cpu, "ram": self.ram, "jobs_running": runnings, "jobs_pending": pendings}

def get_all_hosts(reload_list = False):
	# the hosts are stored in a global array
	if len(HOSTS) == 0 or reload_list:
		# reload_list is True when a client asks for the list
		HOSTS.clear()
		# get the list of hosts from the file
		f = open(config.get("hosts.file.path"), "r")
		for host in f.read().strip("\n").split("\n"):
			# skip the first line (header), this line only contains string and tabs
			if re.search("^[a-zA-Z\\s\\t]+$", host) is not None: continue
			name, address, user, port, rsa_key, cpu, ram = host.split("\t")
			HOSTS.append(Host(name, address, port, user, rsa_key, cpu, ram))
		f.close()
		# make sure the pids directory exists
		if not os.path.isdir(config.PIDS_DIR): os.mkdir(config.PIDS_DIR)
	# return the list
	return HOSTS

def get_highest_cpu():
	# get the highest cpu from the hosts
	highest_cpu = 0
	for host in get_all_hosts():
		if host.cpu > highest_cpu: highest_cpu = int(host.cpu)
	return highest_cpu

def get_highest_ram():
	# get the highest ram from the hosts
	highest_ram = 0
	for host in get_all_hosts():
		if host.ram > highest_ram: highest_ram = int(host.ram)
	return highest_ram

def get_hosts_for_strategy(strategy):
	# get the list of hosts for the given strategy, disregarding the jobs currently running
	# if the strategy is not in the list, return all hosts
	hosts = []
	if strategy == "best_cpu":
		cpu = get_highest_cpu()
		for host in get_all_hosts():
			if host.cpu == cpu: hosts.append(host)
		return hosts
	elif strategy == "best_ram":
		ram = get_highest_ram()
		for host in get_all_hosts():
			if host.ram == ram: hosts.append(host)
		return hosts
	elif strategy == "first_available":
		return get_all_hosts()
	elif strategy.startswith("host:"):
		# the strategy name may contain the name of an host
		host_name = strategy.split(":")[1]
		for host in get_all_hosts():
			if host.name == host_name: hosts.append(host)
		return hosts
	else:
		logger.warning(f"Unknown strategy '{strategy}', returning all hosts")
		return get_all_hosts()

def get_host(host_name):
	matches = list(filter(lambda host: host.name == host_name, get_all_hosts()))
	return None if len(matches) == 0 else matches[0]

def remote_script(host, file):
	# connect to the host
	key = paramiko.RSAKey.from_private_key_file(host.rsa_key)
	ssh = paramiko.SSHClient()
	# TODO use a safer way (get/set_local_hosts)
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	ssh.connect(host.address, port = host.port, username = host.user, pkey = key)
	# execute the script remotely (it will automatically create the pid file)
	# use setsid --fork to make sure the process is detached from the terminal
	# it will also make sure that all processes are killed if user cancels the job
	ssh.exec_command(f"setsid --fork bash {file}")
	# close the connection and return the pid
	ssh.close()

def remote_check(host, pid):
	# this function is now only called as a backup, when the default system is not working
	# each host should have a process that puts all alive pids in a shared file
	# this function is called if this file does not exist, or has not been updated for a while
	# but if we are in this function, it probably means that something is not right on the remote host
	if host is not None and pid is not None and pid > 0:
		# connect to the host
		key = paramiko.RSAKey.from_private_key_file(host.rsa_key)
		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		ssh.connect(host.address, port = host.port, username = host.user, pkey = key)
		# execute the script remotely
		_, stdout, _ = ssh.exec_command(f"ps -p {pid} -o comm= ; echo $?")
		# the process is alive if the command did not fail
		stdout = stdout.read().decode('ascii').strip("\n")
		# logger.debug(f"Remote check: ps -p {pid}: "+stdout)
		is_alive = stdout.splitlines()[-1] == "0"
		# close the connection after dealing with stdout
		ssh.close()
		return is_alive
	return False

def is_alive(host_name, pid):
	# each VM should be storing their current pids in a shared file
	pid_file = f"{config.PIDS_DIR}/{host_name}"
	# check that this file exists and has been changed in the last 2 minutes
	if os.path.isfile(pid_file) and time.time() - os.path.getmtime(pid_file) < 120:
		# check that the pid is in the file
		is_alive = False
		f = open(pid_file, "r")
		for p in f.read().strip("\n").split("\n"):
			if p.lstrip() == pid:
				is_alive = True
				break
		f.close()
		return is_alive
	else:
		# the pid was not found, send a warning and return false
		logger.warning(f"The PID file '{pid_file}' is either not found or not updated for too long, connecting to the host to check if the PID is alive")
		return False

def remote_cancel(host, pid):
	if host is not None and pid is not None and pid > 0:
		# connect to the host
		key = paramiko.RSAKey.from_private_key_file(host.rsa_key)
		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		ssh.connect(host.address, port = host.port, username = host.user, pkey = key)
		# kill the process remotely and all its children
		# TODO does it kill the session too?
		ssh.exec_command(f"kill $(ps -s {pid} -o pid=)")
		# close the connection
		ssh.close()

def write_file(file_path, content):
	f = open(file_path, "w")
	f.write(content + "\n")
	f.close()

def create_job_directory(job_dir_name, form):
	# the job directory will contain some automatically created files:
	# - .cumulus.cmd: the script that will be executed on the host
	# - .cumulus.pid: the pid of the ssh session
	# - .cumulus.rsync: a blank file that is sent once all the files have been transferred
	# - .cumulus.settings: the user settings, it can be useful to know what the job is about without connecting to the interface or to sqlite
	# - .cumulus.stdout: a link to the standard output of the script
	# - .cumulus.stderr: a link to the standard error of the script
	job_dir = f"{config.JOB_DIR}/{job_dir_name}"
	if not os.path.isfile(job_dir): os.mkdir(job_dir)
	# add a .cumulus.settings file with basic information from the database, to make it easier to find proprer folder
	write_file(job_dir + "/.cumulus.settings", json.dumps(form))
	# create a temp folder that the apps may use eventually
	temp_dir = f"{job_dir}/temp"
	if not os.path.isfile(temp_dir): os.mkdir(temp_dir)

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
	for file in os.listdir(config.DATA_DIR):
		filelist.append((file, get_size(config.DATA_DIR + "/" + file)))
	return filelist

def delete_raw_file(file):
	try:
		if os.path.isfile(file): os.remove(file)
		else: shutil.rmtree(file)
	except OSError as o:
		logger.error(f"Can't delete raw file {file}: {o.strerror}")

def delete_job_folder_no_db(job_dir):
	try:
		if os.path.isdir(job_dir): 
			shutil.rmtree(job_dir)
			logger.info(f"Job folder '{job_dir}' has been deleted")
	except OSError as o:
		logger.error(f"Can't delete job folder {job_dir}: {o.strerror}")

def delete_job_folder(job_id, delete_job_in_database = False):
	try:
		job_dir = db.get_job_dir(job_id)
		if job_dir != "" and os.path.isdir(job_dir): 
			shutil.rmtree(job_dir)
			logger.info(f"Job folder '{job_dir}' has been deleted")
		if delete_job_in_database: db.delete_job(job_id)
		return True
	except OSError as o:
		db.set_status(job_id, "FAILED")
		logger.error(f"Can't delete job folder for {db.get_job_to_string(job_id)}: {o.strerror}")
		add_to_stderr(job_id, f"Can't delete job folder for {db.get_job_to_string(job_id)}: {o.strerror}")
		return False

def get_pid_file(job_id): return db.get_job_dir(job_id) + "/.cumulus.pid"

def get_pid(job_id):
	file = get_pid_file(job_id)
	if os.path.isfile(file):
		f = open(file, "r")
		content = f.read()
		f.close()
		return int(content)
	else: return 0

def cancel_job(job_id):
	# get the pid and the host
	pid = get_pid(job_id)
	host_name = db.get_host(job_id)
	# use ssh to kill the pid (may not be needed if the job is still pending)
	remote_cancel(get_host(host_name), pid)
	# change the status
	db.set_status(job_id, "CANCELLED")
	db.set_end_date(job_id)

def add_to_stderr(job_id, text):
	with open(config.get_final_stderr_path(job_id), "a") as f:
		f.write(f"\nCumulus: {text}")

# def get_file_age_in_days(file):
	# # mtime is the date in seconds since epoch since the last modification
	# # time() is the current time
	# # divide by the number of seconds in a day to have the number of days
	# if file is None: return 0
	# t = (time.time() - os.path.getmtime(file)) / 86400
	# logger.debug(f"File '{os.path.basename(file)}': {t}")
	# return t
def get_file_age_in_seconds(file):
	# return 0 if the file is not found or not given
	if file is None: return 0
	if not os.path.isfile(file) and not os.path.isdir(file): return 0
	# mtime is the date in seconds since epoch since the last modification
	# time() is the current time
	# divide by the number of seconds in a day to have the number of days
	t = time.time() - os.path.getmtime(file)
	logger.debug(f"File '{os.path.basename(file)}': {round(t / 86400, 2)} days")
	return t

def get_disk_usage():
	total, used, free = shutil.disk_usage(config.get("storage.path"))
	logger.debug(f"Total: {total} ; Used: {used} ; Free: {free}")
	return total, used, free

# def get_deletable_jobs():
	# # get the max age in seconds
	# max_age_seconds = int(config.get("data.max.age.in.days")) * 86400
	# # get the job ids and directories
	# jobs = db.get_ended_jobs_older_than(max_age_seconds)

def get_zombie_jobs():
	# look at the folders in the main job dir that are not used for jobs
	zombie_job_folders = []
	for job in os.listdir(config.JOB_DIR):
		if os.path.isdir(config.JOB_DIR + "/" + job):
			# jobs look like "Job_{job_id}_{owner}_{app_name}_{str(creation_date)}"
			if re.search("Job_\\d+_", job) == None:
				zombie_job_folders.append(config.JOB_DIR + "/" + job)
			else:
				# the folder looks like a job folder, let's check if its id is in the database
				job_id = int(job.split("_")[1])
				if not db.check_job_existency(job_id): zombie_job_folders.append(config.JOB_DIR + "/" + job)
	return zombie_job_folders

def get_zombie_log_files():
	# list the log files in the main log dir that are not used for jobs
	zombie_log_files = []
	for log in os.listdir(config.LOG_DIR):
		if os.path.isfile(config.LOG_DIR + "/" + log):
			# only consider files that look like logs
			if re.search("job_\\d+\\.stdout", log) != None or re.search("job_\\d+\\.stderr", log) != None:
				# extract the job id from the file name
				job_id = int(log.split("_")[1].split(".")[0])
				# check if the job id is in the database
				if not db.check_job_existency(job_id): zombie_log_files.append(config.LOG_DIR + "/" + log)
	return zombie_log_files

def get_unused_shared_files_older_than(max_age_seconds):
	# list the shared files and folders
	files = []
	for file in os.listdir(config.DATA_DIR):
		file = config.DATA_DIR + "/" + file
		# only consider the files or folders older than the given time
		if get_file_age_in_seconds(file) > max_age_seconds:
			if not db.is_file_in_use(file): files.append(file)
	return files

def set_job_failed(job_id, error_message):
	db.set_status(job_id, "FAILED")
	db.set_end_date(job_id)
	add_to_stderr(job_id, error_message)
	logger.warning(f"Failure of {db.get_job_to_string(job_id)}")
