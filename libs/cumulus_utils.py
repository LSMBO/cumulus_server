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
import subprocess
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
	#def __init__(self, name, address, cpu, ram, volume):
	def __init__(self):
		"""
		Initializes a new instance of the class with the specified parameters.

		Notes: the host contains these information
			name (str): The name of the instance.
			address (str): The network address of the instance.
			user (str): The username to log into the host
			port (int): The port number to connect to.
			cpu (int): The number of CPU cores allocated.
			ram (int): The amount of RAM allocated (in MB or GB).
			volume (str): The name or ID of the volume on which the host is created
			error (str): A message if there is an error during the creation of the volume or host (None otherwise)

		"""
		self.name = None
		self.address = None
		self.user = config.WORKER_USERNAME
		self.port = config.WORKER_PORT
		self.cpu = None
		self.ram = None
		self.volume = None
		self.error = None

	def __str__(self):
		"""
		Return a string representation of the object, displaying the name, address, port, user, CPU, and RAM attributes separated by tabs.
		"""
		return f"{self.name}\t{self.address}\t{self.port}\t{self.user}\t{self.cpu}\t{self.ram}"

def get_host_from_file(host_file):
	"""
	Reads host information from a specified file and returns a Host object.

	Args:
		host_file (str): The path to the file containing host information.

	Returns:
		Host: A Host object populated with data from the file, or None if the file does not exist.
	"""
	if os.path.isfile(host_file):
		host = Host()
		f = open(host_file, "r")
		for line in f.read().strip("\n").split("\n"):
			if line.startswith("name:"): host.name = line.split("name:")[1].strip()
			elif line.startswith("address:"): host.address = line.split("address:")[1].strip()
			elif line.startswith("cpu:"): host.cpu = int(line.split("cpu:")[1].strip())
			elif line.startswith("ram:"): host.ram = int(line.split("ram:")[1].strip())
			elif line.startswith("volume:"): host.volume = line.split("volume:")[1].strip()
			elif line.startswith("error:"): host.error = line.split("error:")[1].strip()
		host.user = config.WORKER_USERNAME
		host.port = config.WORKER_PORT
		f.close()
		return host
	return None

def get_host(job_id):
	# get the job_dir
	job_dir = db.get_job_dir(job_id)
	# return the host from the file
	return get_host_from_file(job_dir + "/" + config.HOST_FILE)

def get_local_hostname():
	return subprocess.run(['hostname'], stdout = subprocess.PIPE).stdout.decode('utf-8').strip()

def remote_script(host, script_with_args):
	"""
	Executes a remote script on a specified host using SSH.

	Connects to the given host using the provided RSA private key, and executes the specified script file remotely in a detached session using `setsid --fork`. This ensures the script runs independently of the SSH session and is properly detached from the terminal.

	Args:
		host: An object containing SSH connection details (address, port, user, rsa_key).
		file: Path to the script file to be executed on the remote host.
		script_with_args (str): The script file to execute, potentially with arguments and output redirections.

	Notes:
		- The function uses `paramiko` for SSH connections.
		- Host key verification is set to automatically add unknown hosts (consider using a safer approach).
		- The SSH connection is closed after the command is executed.
	"""
	# connect to the host
	# key = paramiko.RSAKey.from_private_key_file(host.rsa_key)
	key = paramiko.RSAKey.from_private_key_file(config.CERT_KEY_PATH)
	ssh = paramiko.SSHClient()
	# TODO use a safer way (get/set_local_hosts)
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	ssh.connect(host.address, port = host.port, username = host.user, pkey = key)
	# execute the script remotely (it will automatically create the pid file)
	# use setsid --fork to make sure the process is detached from the terminal
	# it will also make sure that all processes are killed if user cancels the job
	logger.info(f"Executing remotely this command: {script_with_args}")
	_, stdout, stderr = ssh.exec_command(f"setsid --fork bash {script_with_args}")
	logger.debug(f"STDOUT: {stdout.read().decode('utf-8')}")
	logger.debug(f"STDERR: {stderr.read().decode('utf-8')}")
	# close the connection and return the pid
	ssh.close()

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
		# key = paramiko.RSAKey.from_private_key_file(host.rsa_key)
		key = paramiko.RSAKey.from_private_key_file(config.CERT_KEY_PATH)
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
	- .cumulus.log: A merge of the standard output and standard error of the script.

	Additionally, a 'temp' subdirectory is created for temporary files used by applications.
	A 'input' subdirectory is also created for input files.

	Args:
		job_dir_name (str): Name of the job directory to create.
		form (dict): Dictionary containing user/job settings to be saved in .cumulus.settings.
	"""
	job_dir = f"{config.JOB_DIR}/{job_dir_name}"
	if not os.path.isfile(job_dir): os.mkdir(job_dir)
	# add a .cumulus.settings file with basic information from the database, to make it easier to find proprer folder
	write_file(job_dir + "/.cumulus.settings", json.dumps(form))
	# # create a temp folder that the apps may use eventually
	# temp_dir = f"{job_dir}/temp"
	# if not os.path.isfile(temp_dir): os.mkdir(temp_dir)
	# create an input folder that the apps may use eventually
	input_dir = f"{job_dir}/input"
	if not os.path.isfile(input_dir): os.mkdir(input_dir)

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


def delete_folder(folder):
	"""
	Deletes the specified folder and all its contents.

	Args:
		folder (str): The path to the folder to be deleted.

	Returns:
		bool: True if the folder was successfully deleted, False otherwise.

	Side Effects:
		- Removes the folder from the filesystem if it exists.
		- Logs information and errors.

	Raises:
		None. All exceptions are handled internally.
	"""
	try:
		if os.path.isdir(folder): 
			shutil.rmtree(folder)
			logger.info(f"Folder '{folder}' has been deleted")
	except OSError as o:
		logger.error(f"Can't delete folder {folder}: {o.strerror}")

def delete_job_folder(job_id, delete_job_in_database = False, only_delete_content = False):
	job_dir = db.get_job_dir(job_id)
	# do nothing if the job_dir does not exist
	if job_dir == "" or not os.path.isdir(job_dir): return
	# if archive_content is True, we will just delete the input and output folders within the job folder
	if only_delete_content:
		delete_folder(f"{job_dir}/{config.CONFIG["input.folder"]}")
		delete_folder(f"{job_dir}/{config.CONFIG["output.folder"]}")
	# otherwise we will delete the whole job folder
	else:
		delete_folder(job_dir)
	# if delete_job_in_database is True, we will also delete the job from the database
	if delete_job_in_database: db.delete_job(job_id)

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
	If the job is part of a workflow, the same is done for all jobs in the workflow.

	This function retrieves the process ID (PID) and host associated with the given job,
	attempts to terminate the process remotely, and updates the job's status and end date
	in the database.

	Args:
		job_id (int): The unique identifier of the job to cancel.

	Raises:
		Exception: If the job cannot be found, the process cannot be killed, or the database update fails.
	"""
	# get all the jobs in case this is a workflow job
	job_ids = db.get_associated_jobs(job_id)
	# cancel all the corresponding jobs
	for id in job_ids:
		# get the pid and the host
		pid = get_pid(id)
		# use ssh to kill the pid (may not be needed if the job is still pending)
		remote_cancel(get_host(job_id), pid)
		# change the status
		db.set_status(id, "CANCELLED")
		db.set_end_date(id)

# def get_log_file_path(job_id, is_stdout = True):
def get_log_file_path(job_id):
	"""
	Constructs the file path for a job's log file (stdout or stderr).

	Args:
		job_id (str): The unique identifier of the job.
		is_stdout (bool, optional): If True, returns the path for the standard output log file; 
			if False, returns the path for the standard error log file. Defaults to True.

	Returns:
		str: The full path to the specified log file.
	"""
	# log_file_name = ".cumulus.stdout" if is_stdout else ".cumulus.stderr"
	# return f"{db.get_job_dir(job_id)}/{log_file_name}"
	return f"{db.get_job_dir(job_id)}/{config.JOB_LOG_FILE}"

def add_to_log(job_id, prefix, text, add_timestamp = False):
	"""
	Appends a formatted message to the merged log file for a given job.

	Args:
		job_id (int): The identifier of the job whose stderr log should be updated.
		prefix (str): The prefix to prepend to the log message (e.g., "STDERR").
		text (str): The message to append to the stderr log.
	"""
	# merged_log_file = get_log_file_path(job_id)
	# if os.path.isfile(merged_log_file):
	# 	with open(merged_log_file, "a") as f:
	# 		f.write(f"\n[{prefix}] {text}")
	if add_timestamp:
		# date must be like: 2025-09-18 08:57:45 UTC
		dt = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC"
		new_line = f"[{prefix}] {dt} - {text}"
	else:
		new_line = f"[{prefix}] {text}"
	# open the file in append mode and write the new line
	with open(get_log_file_path(job_id), "ab+") as f:
		# make sure there is a newline before writing the new line
		f.seek(0, 2)
		if f.tell() > 0:
			f.seek(-1, 2)
			if f.read(1) != b'\n': f.write(b'\n')
		# write the new line
		f.write(new_line.encode('utf-8'))
		f.write(b'\n')
	# also log as debug
	logger.debug(new_line)

def add_to_stdout(job_id, text):
	add_to_log(job_id, "STDOUT", text)

def add_to_stderr(job_id, text):
	add_to_log(job_id, "STDERR", text)

def add_to_stdalt(job_id, text):
	add_to_log(job_id, "SERVER", text, True)

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
	If the job is part of a workflow, the same is done for all jobs in the workflow.

	Args:
		job_id (int or str): The unique identifier of the job to mark as failed.
		error_message (str): The error message describing the reason for failure.

	Side Effects:
		- Updates the job's status to "FAILED" in the database.
		- Sets the job's end date in the database.
		- Appends the error message to the job's standard error log.
		- Logs a warning message indicating the job failure.
	"""
	# get all the jobs in case this is a workflow job
	job_ids = db.get_associated_jobs(job_id)
	# fail all the jobs in the workflow
	for id in job_ids:
		db.set_status(id, "FAILED")
		db.set_end_date(id)
		add_to_stderr(id, error_message)
	logger.warning(f"Failure of {db.get_job_to_string(job_id)}")

def get_job_current_directory(job_id):
	"""
	Retrieves the directory for a given job ID.
	This function checks if the job directory contains a stop file, indicating that the job has been stopped.
	If the stop file exists, it returns the job directory; otherwise, it returns the temporary job directory.
	Args:
		job_id (int): The unique identifier of the job.
	Returns:
		str: The path to the job directory if the stop file exists, otherwise the temporary job directory.
	"""
	# get the job directory from the database
	return db.get_job_dir(job_id)

def check_flavor(job_id):
	"""
	Checks if the specified flavor is in the list of authorized flavors.
	If the flavor is not authorized, it returns the default flavor from the configuration.
	The default flavor is the flavor with the lowest weight.

	Args:
		job_id (int): The id of the job to check.

	Returns:
		str: The name of the flavor, either the given one or the default one.
	"""
	flavor = db.get_strategy(job_id)
	# check if the flavor is in the list of authorized flavors
	if flavor not in config.FLAVORS:
		logger.warning(f"The flavor '{flavor}' is not in the list of authorized flavors, using the default flavor instead")
		flavor = min(config.FLAVORS, key=lambda flavor: config.FLAVORS[flavor]['weight'])
	# verify that this flavor can be executed (based on the current cumulated weight of all running jobs)
	if config.FLAVORS[flavor]['weight'] + get_current_flavor_cumulated_weight() > config.FLAVORS_MAX_WEIGHT:
		logger.warning(f"The flavor '{flavor}' cannot be used right now, the maximum cumulated weight of all running jobs would be exceeded")
		return None
	return flavor

def get_current_flavor_cumulated_weight():
	"""
	Calculates the cumulative weight of all flavors currently in use by running jobs.

	Returns:
		int: The total weight of all flavors used by jobs with status "RUNNING".
	"""
	total_weight = 0
	for flavor in db.get_currently_running_strategies():
		if flavor in config.FLAVORS:
			total_weight += config.FLAVORS[flavor]['weight']
	return total_weight

def wait_for_volume(volume_name):
	# wait for the volume to become available
	is_available = False
	while not is_available:
		time.sleep(2) # wait for 2 seconds, it should be enough
		# result = subprocess.run([config.OPENSTACK, "volume", "show", volume_name], stdout=subprocess.PIPE)
		# if result.stdout.decode('utf-8').find('available') != -1: is_available = True
		result = subprocess.run([config.OPENSTACK, "volume", "show", volume_name, "-f", "json"], check = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True)
		status = json.loads(result.stdout).get("status")
		logger.debug(f"wait_for_volume({volume_name}) returned status: {status}")
		is_available = status is not None and status == "available"

def get_volume_id(volume_name):
	try:
		# call openstack
		result = subprocess.run([config.OPENSTACK, "volume", "show", volume_name, "-f", "json"], check = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text=True)
		# parse the results
		volume_info = json.loads(result.stdout)
		# return the id
		return volume_info.get("id")
	except subprocess.CalledProcessError as e:
		# if the command fails (usually because the volume does not exist)
		return None

# def is_volume_present(volume_name):
	# # result = subprocess.run([config.OPENSTACK, "volume", "show", volume_name], stdout=subprocess.PIPE)
	# # for line in result.stdout.decode('utf-8').splitlines():
		# # if "No volume with a name or ID" in line:
			# # return False
	# # return True
	# result = subprocess.run([config.OPENSTACK, "volume", "show", volume_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stderr
	# # logger.debug(f"openstack volume show {volume_name} returned: {result}")
	# # return result.find('No volume with a name or ID') == -1
	# return "No volume found for" in result

# def is_server_present(server_name):
	# # result = subprocess.run([config.OPENSTACK, "server", "show", server_name], stderr=subprocess.PIPE, text=True)
	# # for line in result.stdout.decode('utf-8').splitlines():
		# # if "No Server found for" in line:
			# # return False
	# # return True
	# result = subprocess.run([config.OPENSTACK, "server", "show", server_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stderr
	# logger.debug(f"openstack server show {server_name} returned: {result}")
	# # return not "No Server found for" in result
	# return "No Server found for" in result

def get_server_ip_address(server_name):
	try:
		# call openstack
		result = subprocess.run([config.OPENSTACK, "server", "show", server_name, "-f", "json"], check = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text=True)
		# parse the results and search for the first IP address
		server_info = json.loads(result.stdout)
		addresses = server_info.get("addresses")
		if not isinstance(addresses, dict): return None
		# Get the first network and its list of IPs
		for network_ips in addresses.values():
			if isinstance(network_ips, list) and network_ips: return network_ips[0]
		# No IPs found in any network
		return None
	except subprocess.CalledProcessError as e:
		# if the command fails (usually because the server does not exist)
		return None

def clone_volume(job_id):
	# volume_id = None
	# volume_name = f"volume_job_{job_id}"
	# # check that the volume does not already exist
	# if is_volume_present(volume_name): 
		# logger.warn(f"Volume {volume_name} already exists, reusing it")
		# result = subprocess.run([config.OPENSTACK, "volume", "show", volume_name], stdout=subprocess.PIPE)
		# for line in result.stdout.decode('utf-8').splitlines():
			# if " id " in line:
				# volume_id = line.split()[1]
				# break
	# else:
		# add_to_stdalt(job_id, "Creating the volume for the virtual machine...")
		# # result = subprocess.run([config.OPENSTACK, "volume", "create", "--snapshot", config.SNAPSHOT_NAME, "--size", config.VOLUME_SIZE_GB, "--bootable", volume_name], stdout=subprocess.PIPE)
		# for line in result.stdout.decode('utf-8').splitlines():
			# if " id " in line:
				# line = line.strip().replace('|', '').strip() # remove the pipes
				# volume_id = line.split()[1]
				# # return volume_id, volume_name
				# break
		# # check that the volume was created
		# if not is_volume_present(volume_name): 
			# return None, None
		# # wait for the volume to become available
		# wait_for_volume(volume_name)
		# add_to_stdalt(job_id, "The volume has been successfully created")
	# # return the volume id and name
	# return volume_id, volume_name
	logger.debug(f"Clone volume for job {job_id}")
	volume_name = f"volume_job_{job_id}"
	volume_id = get_volume_id(volume_name)
	if volume_id is None:
		# create the volume
		add_to_stdalt(job_id, "Creating the volume for the virtual machine...")
		result = subprocess.run([config.OPENSTACK, "volume", "create", "--snapshot", config.SNAPSHOT_NAME, "--size", config.VOLUME_SIZE_GB, "--bootable", volume_name, "-f", "json"], stdout = subprocess.PIPE, text = True)
		volume_id = json.loads(result.stdout).get("id")
		if volume_id is None:
			return None, None
		# wait for the volume to become available
		wait_for_volume(volume_name)
		add_to_stdalt(job_id, "The volume has been successfully created")
	else:
		# reuse the volume
		logger.warn(f"Volume {volume_name} already exists, reusing it")
	# return the volume id and name
	logger.debug(f"Cloned volume with name {volume_name} and ID {volume_id}")
	return volume_id, volume_name

def ssh_keyscan(ip_address):
	try:
		result = subprocess.run(['ssh-keyscan', '-T', '5', ip_address], stdout = subprocess.PIPE, stderr = subprocess.DEVNULL, text=True)
		return result.stdout.strip()
	except Exception as e:
		return None

def wait_for_server_ssh_access(job_id, ip_address):
	# remove the ip address beforehand
	subprocess.run(['ssh-keygen', '-R', ip_address], stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL, check = True)
	# wait for the server to return an answer
	i = 0
	while True:
		result = ssh_keyscan(ip_address)
		if result and ip_address in result:
			# add the ip address to the known hosts
			with open(config.KNOWN_HOSTS_PATH, 'a') as f: f.write(result + '\n')
			# break the loop
			break
		# wait for 20 seconds before trying again (but only log it once per minute)
		if i == 0:
			add_to_stdalt(job_id, f"Waiting for the virtual machine to be available...")
			i = 3
		time.sleep(20)
		i -= 1
	# wait just a little more to make sure we are allowed to log in
	time.sleep(5)
	add_to_stdalt(job_id, f"The virtual machine is available")

def create_virtual_machine(job_id, flavor, volume_id):
	# worker_name = f"worker_job_{job_id}"
	# ip_address = None
	# # check that the server does not already exist
	# if is_server_present(worker_name): 
		# logger.warn(f"Virtual machine {worker_name} already exists, reusing it")
		# result = subprocess.run([config.OPENSTACK, "server", "show", worker_name], stdout=subprocess.PIPE)
		# for line in result.stdout.decode('utf-8').splitlines():
			# if "addresses" in line:
				# ip_address = line.split()[3].split("=")[1]
				# break
	# else:
		# add_to_stdalt(job_id, "Creating the virtual machine...")
		# result = subprocess.run([config.OPENSTACK, "server", "create", "--flavor", flavor, "--key-name", config.CERT_KEY_NAME, "--security-group", "default", "--network", config.CLOUD_NETWORK, "--wait", "--block-device", f"source_type=volume,uuid={volume_id},boot_index=0,destination_type=volume", worker_name], stdout=subprocess.PIPE)
		# for line in result.stdout.decode('utf-8').splitlines():
			# if " addresses " in line:
				# line = line.strip().replace('|', '').strip() # remove the pipes
				# ip_address = line.split()[1].split("=")[1]
		# # check that the server was created
		# if not is_server_present(worker_name): 
			# return None, None
		# add_to_stdalt(job_id, f"The virtual machine for job '{job_id}' has been successfully created")
	# # wait for the server to be accessible via ssh
	# wait_for_server_ssh_access(job_id, ip_address)
	# # return the worker name and ip address
	# return worker_name, ip_address
	
	logger.debug(f"Create worker for job {job_id}")
	worker_name = f"worker_job_{job_id}"
	ip_address = get_server_ip_address(worker_name)
	if ip_address is None:
		# the worker does not exist yet
		add_to_stdalt(job_id, "Creating the virtual machine...")
		result = subprocess.run([config.OPENSTACK, "server", "create", "--flavor", flavor, "--key-name", config.CERT_KEY_NAME, "--security-group", "default", "--network", config.CLOUD_NETWORK, "--wait", "--block-device", f"source_type=volume,uuid={volume_id},boot_index=0,destination_type=volume", worker_name], stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)
		ip_address = get_server_ip_address(worker_name)
		if ip_address is None: 
			return None, None
		add_to_stdalt(job_id, f"The virtual machine for job '{job_id}' has been successfully created")
	else:
		# reuse the server
		logger.warn(f"Virtual machine {worker_name} already exists, reusing it")
	# wait for the server to be accessible via ssh
	wait_for_server_ssh_access(job_id, ip_address)
	# return the worker name and ip address
	logger.debug(f"Worker has been created with name {worker_name} and IP {ip_address}")
	return worker_name, ip_address

def write_host_file(job_dir, worker_name, ip_address, cpu, ram, volume_name, error):
	if error is not None:
		with open(f"{job_dir}/{config.HOST_FILE}", "w") as f:
			f.write(f"error:{error}\n")
		return
	with open(f"{job_dir}/{config.HOST_FILE}", "w") as f:
		f.write(f"name:{worker_name}\n")
		f.write(f"address:{ip_address}\n")
		f.write(f"cpu:{cpu}\n")
		f.write(f"ram:{ram}\n")
		f.write(f"volume:{volume_name}\n")

def create_worker(job_id, job_dir, flavor):
	"""
	Creates a new worker VM with the specified flavor.

	Args:
		flavor (str): The flavor to use for the new worker VM.

	Returns:
		Host: The Host object representing the newly created worker VM.
	"""
	logger.info(f"Creating a virtual machine with flavor '{flavor}' for job {job_id}")
	# job_dir = db.get_job_dir(job_id)
	# clone the volume from the template
	volume_id, volume_name = clone_volume(job_id)
	# abord if the volume could not be created
	if volume_id is None or volume_name is None:
		logger.error(f"Cannot create the volume for job {job_id}, aborting")
		add_to_stdalt(job_id, f"Cannot create the volume for job {job_id}, aborting")
		write_host_file(job_dir, None, None, None, None, None, "Cannot create the volume")
		return
	# create a worker VM based on this volume
	worker_name, ip_address = create_virtual_machine(job_id, flavor, volume_id)
	# abord if the vm could not be created
	if worker_name is None or ip_address is None:
		logger.error(f"Cannot create the virtual machine for job {job_id}, aborting")
		add_to_stdalt(job_id, f"Cannot create the virtual machine for job {job_id}, aborting")
		write_host_file(job_dir, None, None, None, None, None, "Cannot create the virtual machine")
		# delete the volume
		subprocess.run([config.OPENSTACK, "volume", "delete", volume_name])
		return
	# get the cpu and ram from the flavor
	cpu = config.FLAVORS[flavor]['cpu']
	ram = config.FLAVORS[flavor]['ram']
	# create a host object to represent this worker
	logger.info(f"Worker VM '{worker_name}' has been created for job {job_id}")
	write_host_file(job_dir, worker_name, ip_address, cpu, ram, volume_name, None)

# def destroy_worker(job_id):
	# """
	# Destroys the worker VM associated with the given job ID.

	# Args:
		# job_id (int): The unique identifier of the job whose worker VM is to be destroyed.

	# Returns:
		# bool: True if the worker VM was successfully destroyed, False otherwise.
	# """
	# logger.info(f"Destroying the virtual machine for job {job_id}")
	# host = get_host(job_id)
	# if host is not None:
		# # delete the VM
		# subprocess.run([config.OPENSTACK, "server", "delete", "--wait", host.name])
		# # delete the volume
		# subprocess.run([config.OPENSTACK, "volume", "delete", host.volume])
		# logger.info(f"Worker VM '{host.name}' has been destroyed for job {job_id}")
		# return True
	# else:
		# logger.error(f"Cannot destroy the virtual machine for job {job_id}, host information not found")
		# return False

def destroy_worker(job_id):
	"""
	Destroys the worker VM associated with the given job ID.
	If the job is part of a workflow, the same is done for all jobs in the workflow.
	This function should be called in a thread

	Args:
		job_id (int): The unique identifier of the job whose worker VM is to be destroyed.

	Returns:
		bool: True if the worker VM (and its related VMs) was successfully destroyed, False otherwise.
	"""
	logger.info(f"Destroying the virtual machine for job {job_id}")
	# get all the jobs in case this is a workflow job
	job_ids = db.get_associated_jobs(job_id)
	# cancel all the corresponding jobs
	all_workers_destroyed = False
	for id in job_ids:
		host = get_host(job_id)
		# destroy the session
		if host is not None:
			# delete the VM
			subprocess.run([config.OPENSTACK, "server", "delete", "--wait", host.name])
			# delete the volume
			subprocess.run([config.OPENSTACK, "volume", "delete", host.volume])
			logger.info(f"Worker VM '{host.name}' has been destroyed for job {job_id}")
			all_workers_destroyed = True
		else:
			logger.error(f"Cannot destroy the virtual machine for job {job_id}, host information not found")
			all_workers_destroyed = False
	return all_workers_destroyed

def get_mzml_file_path(file_path, use_temp_dir = False):
	"""
	Replaces the extension of the given file path with '.mzML' and returns the new path.
	This is useful to know in advance what the file name will be after conversion to mzML.

	Args:
		file_path (str): The original file path.
		use_temp_dir (bool): If True, the returned path will be in the temporary directory. Defaults to False.

	Returns:
		str: The file path with its extension replaced by '.mzML'.
	"""
	# replace the extension of the file by .mzML and return the path
	mzml_file_path = file_path.replace(os.path.splitext(file_path)[1], f".mzML")
	# if use_temp_dir is True, return the path in the temp dir
	if use_temp_dir:
		mzml_file_path = f"{config.TEMP_DIR}/{os.path.basename(mzml_file_path)}"
	# return the new file path
	return mzml_file_path

def convert_to_mzml(job_id, file):
	# prepare the output and temp file names
	temp_output_file = get_mzml_file_path(file, True)
	final_output_file = get_mzml_file_path(file, False)
	# call the appropriate converter command based on the file extension
	if file.endswith(".d"): 
		logger.info(f"Converting Bruker data {os.path.basename(file)} to mzML")
		# subprocess.run([config.get("converter.d.to.mzml"), "-i", file, "-o", temp_output_file])
		add_to_stdalt(job_id, f"Converting Bruker data {os.path.basename(file)} to mzML")
		with open(get_log_file_path(job_id), "a") as log_file:
			subprocess.run([config.get("converter.d.to.mzml"), "-i", file, "-o", temp_output_file], stdout = log_file, stderr = log_file, text = True)
	elif file.endswith(".raw"): 
		logger.info(f"Converting Thermo raw file {os.path.basename(file)} to mzML")
		# subprocess.run(["mono", config.get("converter.raw.to.mzml"), "-i", file, "-b", temp_output_file])
		add_to_stdalt(job_id, f"Converting Thermo raw file {os.path.basename(file)} to mzML")
		with open(get_log_file_path(job_id), "a") as log_file:
			subprocess.run(["mono", config.get("converter.raw.to.mzml"), "-i", file, "-b", temp_output_file], stdout = log_file, stderr = log_file, text = True)
	else:
		logger.error(f"Cannot convert file '{file}' to mzML, unknown extension")
	# move the file to the final location
	if os.path.isfile(temp_output_file): shutil.move(temp_output_file, final_output_file)

# def get_job_usage(job_id):
# 	"""
# 	Searches for the file JOB_USAGE_FILE in the job directory and returns its content as a string.

# 	Args:
# 		job_id (int): The unique identifier of the job.

# 	Returns:
# 		str: The content of the file, or an empty string if the file does not exist.
# 	"""
# 	job_dir = db.get_job_dir(job_id)
# 	job_usage_file = f"{job_dir}/{config.JOB_USAGE_FILE}"
# 	if os.path.isfile(job_usage_file):
# 		f = open(job_usage_file, "r")
# 		content = f.read()
# 		f.close()
# 		return content
# 	else: return ""