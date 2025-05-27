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
	"""
	Represents a remote host with computational resources.

	Attributes:
		name (str): The name of the host.
		address (str): The network address of the host.
		port (int): The port number for connecting to the host.
		user (str): The username for authentication.
		rsa_key (str): The RSA key for secure authentication.
		cpu (int): The number of CPU cores available on the host.
		ram (int): The amount of RAM (in GB or MB) available on the host.

	Methods:
		__init__(name, address, port, user, rsa_key, cpu, ram):
			Initializes a Host instance with the specified parameters.

		__str__():
			Returns a tab-separated string representation of the host's main attributes.

		to_dict():
			Returns a dictionary containing the host's name, CPU, RAM, and the number of running and pending jobs.
	"""
	# TODO maybe add a max number of jobs per host?
	def __init__(self, name, address, port, user, rsa_key, cpu, ram):
		"""
		Initializes a new instance of the class with the specified parameters.

		Args:
			name (str): The name of the instance.
			address (str): The network address of the instance.
			port (int): The port number to connect to.
			user (str): The username for authentication.
			rsa_key (str): The RSA key for secure access.
			cpu (int): The number of CPU cores allocated.
			ram (int): The amount of RAM allocated (in MB or GB).

		"""
		self.name = name
		self.address = address
		self.port = port
		self.user = user
		self.rsa_key = rsa_key
		self.cpu = int(cpu)
		self.ram = int(ram)

	def __str__(self):
		"""
		Return a string representation of the object, displaying the name, address, port, user, CPU, and RAM attributes separated by tabs.
		"""
		return f"{self.name}\t{self.address}\t{self.port}\t{self.user}\t{self.cpu}\t{self.ram}"
	
	def to_dict(self):
		"""
		Converts the host object to a dictionary representation, including job statistics.

		Returns:
			dict: A dictionary containing the host's name, CPU, RAM, number of running jobs, and number of pending jobs.
		"""
		pendings, runnings = db.get_alive_jobs_per_host(self.name)
		return {"name": self.name, "cpu": self.cpu, "ram": self.ram, "jobs_running": runnings, "jobs_pending": pendings}

def get_all_hosts(reload_list = False):
	"""
	Retrieves and returns a list of all host objects.

	If the global HOSTS list is empty or if `reload_list` is True, the function reloads the host information
	from a file specified in the configuration. It skips the header line in the file, parses each host entry,
	and appends Host objects to the HOSTS list. It also ensures that the directory for storing process IDs exists.

	Args:
		reload_list (bool): If True, forces reloading the host list from the file. Defaults to False.

	Returns:
		list: A list of Host objects representing all available hosts.
	"""
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
	"""
	Returns the highest CPU value among all hosts.

	Iterates through all hosts retrieved by `get_all_hosts()` and determines the maximum CPU value.
	Assumes each host object has a `cpu` attribute.

	This function is useful for determining the most powerful host available for job scheduling.

	Returns:
		int: The highest CPU value found among the hosts. Returns 0 if no hosts are found.
	"""
	# get the highest cpu from the hosts
	highest_cpu = 0
	for host in get_all_hosts():
		if host.cpu > highest_cpu: highest_cpu = int(host.cpu)
	return highest_cpu

def get_highest_ram():
	"""
	Returns the highest RAM value among all hosts.

	Iterates through all available hosts and determines the maximum RAM value.
	Assumes each host object has a 'ram' attribute representing its RAM size.

	This function is useful for identifying the host with the most memory available for job execution.

	Returns:
		int: The highest RAM value found among the hosts.
	"""
	# get the highest ram from the hosts
	highest_ram = 0
	for host in get_all_hosts():
		if host.ram > highest_ram: highest_ram = int(host.ram)
	return highest_ram

def get_hosts_for_strategy(strategy):
	"""
	Returns a list of hosts based on the specified selection strategy.

	Args:
		strategy (str): The strategy to use for selecting hosts. Supported strategies are:
			- "best_cpu": Selects hosts with the highest CPU.
			- "best_ram": Selects hosts with the highest RAM.
			- "first_available": Returns all available hosts.
			- "host:<name>": Selects the host with the specified name.
			- Any other value: Returns all hosts and logs a warning.

	Returns:
		list: A list of host objects matching the selection strategy.

	Notes:
		- The function disregards jobs currently running on the hosts.
		- If the strategy is unknown, all hosts are returned and a warning is logged.
	"""
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
	"""
	Retrieves a host object by its name from the list of all hosts.

	Args:
		host_name (str): The name of the host to retrieve.

	Returns:
		Host or None: The host object with the specified name if found, otherwise None.
	"""
	matches = list(filter(lambda host: host.name == host_name, get_all_hosts()))
	return None if len(matches) == 0 else matches[0]

def remote_script(host, file):
	"""
	Executes a remote script on a specified host using SSH.

	Connects to the given host using the provided RSA private key, and executes the specified script file remotely in a detached session using `setsid --fork`. This ensures the script runs independently of the SSH session and is properly detached from the terminal.

	Args:
		host: An object containing SSH connection details (address, port, user, rsa_key).
		file: Path to the script file to be executed on the remote host.

	Notes:
		- The function uses `paramiko` for SSH connections.
		- Host key verification is set to automatically add unknown hosts (consider using a safer approach).
		- The SSH connection is closed after the command is executed.
	"""
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
	"""
	Checks if a process with a given PID is alive on a remote host via SSH.

	This function attempts to connect to a remote host using SSH and checks if a process
	with the specified PID is running by executing the `ps` command remotely. It is intended
	as a backup method when the default system for tracking alive PIDs is not working.

	Args:
		host: An object representing the remote host, expected to have attributes
			`address` (str), `port` (int), `user` (str), and `rsa_key` (str, path to private key).
		pid (int): The process ID to check on the remote host.

	Returns:
		bool: True if the process is alive on the remote host, False otherwise.
	"""
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
	"""
	Checks if a process with the given PID is alive on the specified host.

	This function verifies the existence and freshness (modified within the last 2 minutes)
	of a PID file associated with the host. It then checks if the specified PID is listed
	in the file. If the file is missing, outdated, or the PID is not found, a warning is logged.

	Args:
		host_name (str): The name of the host whose PID file should be checked.
		pid (str): The process ID to look for in the PID file.

	Returns:
		bool: True if the PID is found in a recent PID file, False otherwise.
	"""
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
	"""
	Terminates a remote process and all its child processes on a specified host via SSH.

	Args:
		host: An object containing SSH connection details (address, port, user, rsa_key).
		pid (int): The process ID of the remote process to terminate.

	Raises:
		paramiko.ssh_exception.SSHException: If an SSH-related error occurs.
		FileNotFoundError: If the RSA private key file is not found.
		Exception: For other unforeseen errors during SSH connection or command execution.

	Note:
		The function uses the `kill $(ps -s {pid} -o pid=)` command to terminate the process group.
	"""
	if host is not None and pid is not None and pid > 0:
		# connect to the host
		key = paramiko.RSAKey.from_private_key_file(host.rsa_key)
		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		ssh.connect(host.address, port = host.port, username = host.user, pkey = key)
		# kill the process remotely and all its children
		ssh.exec_command(f"kill $(ps -s {pid} -o pid=)")
		# close the connection
		ssh.close()

def write_file(file_path, content):
	"""
	Writes the given content to a file at the specified file path.

	Parameters:
		file_path (str): The path to the file where the content will be written.
		content (str): The content to write to the file.

	The function overwrites the file if it already exists and appends a newline character at the end of the content.
	"""
	f = open(file_path, "w")
	f.write(content + "\n")
	f.close()

def create_job_directory(job_dir_name, form):
	"""
	Creates a job directory with the specified name and initializes required files and subdirectories.

	The job directory will contain the following automatically created files:
	- .cumulus.cmd: Script to be executed on the host.
	- .cumulus.pid: PID of the SSH session.
	- .cumulus.rsync: Blank file sent after all files are transferred.
	- .cumulus.settings: User settings in JSON format, useful for identifying the job.
	- .cumulus.stdout: Link to the standard output of the script.
	- .cumulus.stderr: Link to the standard error of the script.

	Additionally, a 'temp' subdirectory is created for temporary files used by applications.

	Args:
		job_dir_name (str): Name of the job directory to create.
		form (dict): Dictionary containing user/job settings to be saved in .cumulus.settings.
	"""
	job_dir = f"{config.JOB_DIR}/{job_dir_name}"
	if not os.path.isfile(job_dir): os.mkdir(job_dir)
	# add a .cumulus.settings file with basic information from the database, to make it easier to find proprer folder
	write_file(job_dir + "/.cumulus.settings", json.dumps(form))
	# create a temp folder that the apps may use eventually
	temp_dir = f"{job_dir}/temp"
	if not os.path.isfile(temp_dir): os.mkdir(temp_dir)

def get_size(file):
	"""
	Calculate the size of a file or the total size of all files within a directory.

	Args:
		file (str): Path to the file or directory.

	Returns:
		int: Size in bytes. If a file is provided, returns its size. If a directory is provided,
			 returns the cumulative size of all contained files (excluding symbolic links).

	Raises:
		OSError: If the file or directory does not exist or is inaccessible.
	"""
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
	"""
	Retrieves a list of files from the configured data directory along with their sizes.

	Returns:
		list of tuple: A list where each tuple contains the filename (str) and its size (int) in bytes.
	
	Notes:
	- The tags Raw/Fasta will be replaced by Shared/Local in the future.
	"""
	filelist = []
	for file in os.listdir(config.DATA_DIR):
		filelist.append((file, get_size(config.DATA_DIR + "/" + file)))
	return filelist

def delete_raw_file(file):
	"""
	Deletes the specified file or directory.

	If the given path is a file, it removes the file.
	If the given path is a directory, it removes the directory and all its contents.
	Logs an error message if the deletion fails.

	Args:
		file (str): Path to the file or directory to delete.

	Raises:
		Logs an error if the file or directory cannot be deleted.

	Notes:
	- The tag Raw/Fasta will be replaced by Shared/Local in the future.
	"""
	try:
		if os.path.isfile(file): os.remove(file)
		else: shutil.rmtree(file)
	except OSError as o:
		logger.error(f"Can't delete raw file {file}: {o.strerror}")

def delete_job_folder_no_db(job_dir):
	"""
	Deletes the specified job directory from the filesystem without interacting with the database.
	It is used when the cleaning daemon determines that a job directory has to be removed, in this
	case we want to keep the job in the database (with an specific status).
	The difference with `delete_job_folder` is that this function cannot change the job's status in the database.

	Args:
		job_dir (str): The path to the job directory to be deleted.

	Logs:
		- Info: If the job directory is successfully deleted.
		- Error: If the job directory cannot be deleted due to an OSError.

	Exceptions:
		Does not raise exceptions; errors are logged.
	"""
	try:
		if os.path.isdir(job_dir): 
			shutil.rmtree(job_dir)
			logger.info(f"Job folder '{job_dir}' has been deleted")
	except OSError as o:
		logger.error(f"Can't delete job folder {job_dir}: {o.strerror}")

def delete_job_folder(job_id, delete_job_in_database = False):
	"""
	Deletes the job folder associated with the given job ID and optionally removes the job from the database.

	Args:
		job_id (int or str): The unique identifier of the job whose folder is to be deleted.
		delete_job_in_database (bool, optional): If True, also deletes the job entry from the database. Defaults to False.

	Returns:
		bool: True if the job folder (and optionally the database entry) was successfully deleted, False otherwise.

	Side Effects:
		- Removes the job directory from the filesystem if it exists.
		- Logs information and errors.
		- Updates the job status to "FAILED" in the database if an error occurs.
		- Appends error messages to the job's stderr log.

	Raises:
		None. All exceptions are handled internally.
	"""
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

def get_pid_file(job_id): 
	"""
	Returns the file path to the PID file associated with a given job ID.

	Args:
		job_id (int): The unique identifier for the job.

	Returns:
		str: The full path to the '.cumulus.pid' file within the job's directory.
	"""
	return db.get_job_dir(job_id) + "/.cumulus.pid"

def get_pid(job_id):
	"""
	Retrieve the process ID (PID) associated with a given job ID.

	Args:
		job_id (int): The identifier of the job whose PID is to be retrieved.

	Returns:
		int: The PID read from the corresponding PID file if it exists, otherwise 0.
	"""
	file = get_pid_file(job_id)
	if os.path.isfile(file):
		f = open(file, "r")
		content = f.read()
		f.close()
		return int(content)
	else: return 0

def cancel_job(job_id):
	"""
	Cancels a running or pending job by its job ID.

	This function retrieves the process ID (PID) and host associated with the given job,
	attempts to terminate the process remotely, and updates the job's status and end date
	in the database.

	Args:
		job_id (int): The unique identifier of the job to cancel.

	Raises:
		Exception: If the job cannot be found, the process cannot be killed, or the database update fails.
	"""
	# get the pid and the host
	pid = get_pid(job_id)
	host_name = db.get_host(job_id)
	# use ssh to kill the pid (may not be needed if the job is still pending)
	remote_cancel(get_host(host_name), pid)
	# change the status
	db.set_status(job_id, "CANCELLED")
	db.set_end_date(job_id)

def add_to_stderr(job_id, text):
	"""
	Appends a formatted message to the standard error log file for a given job.

	Args:
		job_id (int): The identifier of the job whose stderr log should be updated.
		text (str): The message to append to the stderr log.

	Notes:
		The message is prefixed with 'Cumulus:' and appended as a new line to the log file.
	"""
	with open(config.get_final_stderr_path(job_id), "a") as f:
		f.write(f"\nCumulus: {text}")


def get_file_age_in_seconds(file):
	"""
	Returns the age of a file or directory in seconds since its last modification.

	Parameters:
		file (str or None): The path to the file or directory. If None or the path does not exist, returns 0.

	Returns:
		float: The number of seconds since the file or directory was last modified. Returns 0 if the file is not found or not given.

	Logs:
		Logs the age of the file in days at debug level.
	"""
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
	"""
	Retrieves the total, used, and free disk space for the storage path specified in the configuration.
	This function is called by the client to display the disk usage information. It is also called by 
	the RSync Agent to check if there is enough space to transfer files.

	Returns:
		tuple: A tuple containing three integers:
			- total (int): Total disk space in bytes.
			- used (int): Used disk space in bytes.
			- free (int): Free disk space in bytes.

	Logs:
		Debug information about the total, used, and free disk space.
	"""
	total, used, free = shutil.disk_usage(config.get("storage.path"))
	logger.debug(f"Total: {total} ; Used: {used} ; Free: {free}")
	return total, used, free

def get_zombie_jobs():
	"""
	Scans the main job directory for "zombie" job folders that do not correspond to active jobs.

	A zombie job folder is defined as:
	- A folder in the job directory that does not match the expected job folder naming pattern, or
	- A folder that matches the job folder naming pattern but whose job ID does not exist in the database.

	Returns:
		list: A list of absolute paths to zombie job folders.

	Warning:
	- If you are running a development version of Cumulus on the same machine, with a different database, this will consider that all jobs have to be removed.
	"""
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
	"""
	Scans the main log directory for log files that are not associated with any existing job in the database.

	Returns:
		list: A list of file paths to log files (matching 'job_<id>.stdout' or 'job_<id>.stderr') 
			  that do not correspond to any job present in the database.

	Notes:
		- Relies on `config.LOG_DIR` for the log directory path.
		- Uses `db.check_job_existency(job_id)` to verify if a job exists.
		- Only files matching the log filename patterns are considered.
	"""
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
	"""
	Returns a list of shared files and folders in the configured data directory that are not currently in use and are older than the specified maximum age.

	Args:
		max_age_seconds (int): The minimum age in seconds a file or folder must be to be considered unused.

	Returns:
		list: A list of file and folder paths that are not in use and are older than max_age_seconds.

	Note:
		This function relies on the external `config.DATA_DIR`, `get_file_age_in_seconds`, and `db.is_file_in_use` for its operation.
	"""
	# list the shared files and folders
	files = []
	for file in os.listdir(config.DATA_DIR):
		file = config.DATA_DIR + "/" + file
		# only consider the files or folders older than the given time
		if get_file_age_in_seconds(file) > max_age_seconds:
			if not db.is_file_in_use(file): files.append(file)
	return files

def set_job_failed(job_id, error_message):
	"""
	Marks the specified job as failed, records the error message, and logs the failure.

	Args:
		job_id (int or str): The unique identifier of the job to mark as failed.
		error_message (str): The error message describing the reason for failure.

	Side Effects:
		- Updates the job's status to "FAILED" in the database.
		- Sets the job's end date in the database.
		- Appends the error message to the job's standard error log.
		- Logs a warning message indicating the job failure.
	"""
	db.set_status(job_id, "FAILED")
	db.set_end_date(job_id)
	add_to_stderr(job_id, error_message)
	logger.warning(f"Failure of {db.get_job_to_string(job_id)}")
