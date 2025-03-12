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

CONFIG_FILE_PATH = "cumulus.conf"
DEFAULT_CONFIG_FILE_PATH = "cumulus.conf.default"
CONFIG = {}
DATA_DIR = ""
JOB_DIR = ""
PIDS_DIR = ""
LOG_DIR = ""

def load(config_file_path):
	# clear the current config
	CONFIG.clear()
	# if the file does not exist, use the default one
	if not os.path.isfile(config_file_path):
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

def get(key): 
	if len(CONFIG) == 0: load(CONFIG_FILE_PATH)
	return CONFIG[key]

def init(create_dirs = True):
	# initialize the paths
	global DATA_DIR, JOB_DIR, PIDS_DIR, LOG_DIR
	DATA_DIR = get("storage.path") + get("storage.data.subpath")
	JOB_DIR = get("storage.path") + get("storage.jobs.subpath")
	PIDS_DIR = get("storage.path") + get("storage.pids.subpath")
	LOG_DIR = get("storage.path") + get("storage.logs.subpath")
	# create the directories if needed
	if create_dirs:
		if not os.path.isdir(DATA_DIR): os.mkdir(DATA_DIR)
		if not os.path.isdir(JOB_DIR): os.mkdir(JOB_DIR)
		if not os.path.isdir(PIDS_DIR): os.mkdir(PIDS_DIR)
		if not os.path.isdir(LOG_DIR): os.mkdir(LOG_DIR)

def export():
	return {
		"output.folder": CONFIG["output.folder"],
		"temp.folder": CONFIG["temp.folder"],
		"data.max.age.in.days": CONFIG["data.max.age.in.days"],
		"controller.version": CONFIG["version"],
		"client.min.version": CONFIG["client.min.version"]
	}

def get_final_stdout_path(job_id):
	return f"{LOG_DIR}/job_{job_id}.stdout"

def get_final_stderr_path(job_id):
	return f"{LOG_DIR}/job_{job_id}.stderr"
