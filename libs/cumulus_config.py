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

import os
import re

CONTROLLER_NAME = ""
CONFIG_FILE_PATH = "cumulus.conf"
DEFAULT_CONFIG_FILE_PATH = "cumulus.conf.default"
DEFAULT_FLAVORS_FILE_PATH = "flavors.tsv.default"
JOB_START_FILE = "start_job.sh"
JOB_ALIVE_FILE = ".cumulus.alive"
JOB_STOP_FILE = ".cumulus.stop"
# JOB_USAGE_FILE = ".cumulus.usage"
JOB_LOG_FILE = ".cumulus.log"
HOST_FILE = ".cumulus.host"
CONFIG = {}

DATA_DIR = ""
JOB_DIR = ""
BIN_DIR = ""
TEMP_DIR = ""

OPENSTACK = ""
WORKER_USERNAME = ""
WORKER_PORT = ""
SNAPSHOT_NAME = ""
VOLUME_SIZE_GB = ""
CERT_KEY_NAME = ""
CLOUD_NETWORK = ""
KNOWN_HOSTS_PATH = ""

# predefined flavors and their weight
FLAVORS_MAX_WEIGHT = 1
FLAVORS = {}

def set_controller_name(name):
	"""
	Sets the name of the controller. It should be called just once at the beginning of the program.
	Args:
		name (str): The name of the controller.
	"""
	global CONTROLLER_NAME
	CONTROLLER_NAME = name

def load_flavors():
	global FLAVORS_MAX_WEIGHT, FLAVORS
	# if the flavors file path is not defined, use the default one
	if "flavors.file.path" not in CONFIG:
		CONFIG["flavors.file.path"] = DEFAULT_FLAVORS_FILE_PATH
	f = open(CONFIG["flavors.file.path"], "r")
	for flavor in f.read().strip("\n").split("\n"):
		# skip the first line (header), this line only contains string and tabs
		if re.search("^[a-zA-Z\\s\\t]+$", flavor) is not None: continue
		# if the line contains MAX_ACCUMULATED_WEIGHT, set the global variable and skip the line
		if "MAX_ACCUMULATED_WEIGHT" in flavor: 
			FLAVORS_MAX_WEIGHT = int(flavor.split("=")[1].strip())
			continue
		# otherwise, the line should contain a flavor definition with name, weight, cpu and ram
		name, weight, cpu, ram = flavor.split("\t")
		FLAVORS[name] = { "weight": int(weight), "cpu": int(cpu), "ram": int(ram) }
	f.close()

def load(config_file_path):
	"""
	Loads configuration key-value pairs from a file into the global CONFIG dictionary.

	The function clears the existing CONFIG dictionary, then attempts to read configuration
	data from the specified file. If the file does not exist, it falls back to a default
	configuration file path. Each line in the configuration file is processed to remove comments
	(denoted by '#' or '//'), and lines containing key-value pairs separated by '=' are parsed
	and added to CONFIG with whitespace trimmed from keys and values.

	Args:
		config_file_path (str): Path to the configuration file to load.

	Side Effects:
		Modifies the global CONFIG dictionary with the loaded configuration values.
	"""
	# clear the current config
	CONFIG.clear()
	# if the file does not exist, use the default one
	print("Loading configuration from", config_file_path)
	if not os.path.isfile(config_file_path):
		print(f"Warning: configuration file '{config_file_path}' not found, using default '{DEFAULT_CONFIG_FILE_PATH}'")
		config_file_path = DEFAULT_CONFIG_FILE_PATH
	# get the list of hosts from the file
	f = open(config_file_path, "r")
	for line in f.read().strip("\n").split("\n"):
		# do not consider comments (anything after // or #)
		line = re.sub(r"\s*\t*#.*", "", line.replace("//", "#"))
		# if the line still contains a key and a value
		if "=" in line:
			key, value = line.split("=")
			# trim everything on both sides
			CONFIG[key.strip()] = value.strip()
	f.close()
	# load the flavors
	load_flavors()

def get(key): 
	"""
	Retrieve the value associated with the given key from the configuration.

	If the configuration has not been loaded yet, it loads the configuration
	from the file specified by CONFIG_FILE_PATH before retrieving the value.

	Args:
		key (str): The key whose value should be retrieved from the configuration.

	Returns:
		Any: The value associated with the specified key.

	Raises:
		KeyError: If the key is not found in the configuration.
	"""
	if len(CONFIG) == 0: load(CONFIG_FILE_PATH)
	return CONFIG[key]

def init(create_dirs = True):
	"""
	Initializes global directory paths for data, jobs, PIDs, and logs based on configuration values.

	Parameters:
		create_dirs (bool): If True, creates the directories if they do not exist. Defaults to True.

	Side Effects:
		- Sets global variables.
		- Optionally creates the directories on the filesystem if they are missing.

	Raises:
		OSError: If directory creation fails.
	"""
	# initialize the paths
	global DATA_DIR, JOB_DIR, BIN_DIR, TEMP_DIR, OPENSTACK, WORKER_USERNAME, WORKER_PORT, SNAPSHOT_NAME, VOLUME_SIZE_GB, CERT_KEY_NAME, CLOUD_NETWORK, KNOWN_HOSTS_PATH
	DATA_DIR = get("storage.path") + get("storage.data.subpath")
	JOB_DIR = get("storage.path") + get("storage.jobs.subpath")
	BIN_DIR = get("storage.path") + get("storage.bin.subpath")
	TEMP_DIR = get("storage.path") + get("storage.temp.subpath")
	# WORKSPACE_DIR = get("storage.path") + get("storage.workspace.subpath")
	# WORKSPACES_DIR = get("storage.path") + get("storage.workspaces.subpath")
	OPENSTACK = get("openstack.bin.path")
	WORKER_USERNAME = get("openstack.worker.username")
	WORKER_PORT = get("openstack.worker.port")
	SNAPSHOT_NAME = get("openstack.snapshot.name")
	VOLUME_SIZE_GB = get("openstack.volume.size.gb")
	CERT_KEY_NAME = get("openstack.cert.key.name")
	CLOUD_NETWORK = get("openstack.cloud.network")
	KNOWN_HOSTS_PATH = get("openstack.known.hosts.path")
	# create the directories if needed
	if create_dirs:
		if not os.path.isdir(DATA_DIR): os.mkdir(DATA_DIR)
		if not os.path.isdir(JOB_DIR): os.mkdir(JOB_DIR)
		if not os.path.isdir(BIN_DIR): os.mkdir(BIN_DIR)
		if not os.path.isdir(TEMP_DIR): os.mkdir(TEMP_DIR)
		# if not os.path.isdir(WORKSPACE_DIR): os.mkdir(WORKSPACE_DIR)
		# if not os.path.isdir(WORKSPACES_DIR): os.mkdir(WORKSPACES_DIR)

def export():
	"""
	Exports selected configuration values as a dictionary. Not all configuration keys are included, only what is relevant for an outside caller.

	Returns:
		dict: A dictionary containing the following configuration keys and their corresponding values:
			- "output.folder": The output folder path.
			- "temp.folder": The temporary folder path.
			- "data.max.age.in.days": The maximum age of data in days.
			- "controller.version": The version of the controller.
			- "client.min.version": The minimum required client version.
	"""
	# return dict
	return {
		"input.folder": CONFIG["input.folder"],
		"output.folder": CONFIG["output.folder"],
		"temp.folder": CONFIG["temp.folder"],
		"data.max.age.in.days": CONFIG["data.max.age.in.days"],
		"controller.version": CONFIG["version"],
		"client.min.version": CONFIG["client.min.version"],
		"openstack.max.flavor": str(FLAVORS_MAX_WEIGHT)
	}

def get_temp_job_dir(job_dir):
	# replace the path /cumulus/jobs/ with /cumulus/temp/
	return job_dir.replace(JOB_DIR, TEMP_DIR)
