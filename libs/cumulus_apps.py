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

import logging
import os
import xml.etree.ElementTree as ET

import cumulus_server.libs.cumulus_config as config
import cumulus_server.libs.cumulus_database as db
import cumulus_server.libs.cumulus_utils as utils
# TODO comment the following apps import
import cumulus_server.apps.diann181 as diann181
import cumulus_server.apps.diann191 as diann191
import cumulus_server.apps.test_app as test

logger = logging.getLogger(__name__)
FINAL_FILE = config.get("final.file")
OUTPUT_DIR = config.get("output.folder")
APPS = {}

###################################
#   NEW FUNCTIONS FOR XML FILES   #
###################################

def get_app_list():
	app_list = []
	for f in os.listdir("apps"):
		# TODO f path may be wrong
		if f.endswith(".xml"):
			# store the link between the id of the app and the content of the file
			id = ET.parse(f).getroot().attrib["id"]
			#APPS[id] = f
			# get the xml content
			with open(f, 'r') as xml:
				APPS[id] = xml.read()
				#app_list.append(xml.read())
	#return app_list
	return APPS

################################################
#   PREVIOUS FUNCTIONS UPDATED FOR XML FILES   #
################################################

def is_finished(app_name, stdout):
	#if app_name == "diann_1.8.1": return diann181.is_finished(stdout)
	#elif app_name == "diann_1.9.1": return diann191.is_finished(stdout)
	#elif app_name == "test": return test.is_finished(stdout)
	#else: return True
	if app_name in APPS:
		# extract the end tag from the app xml file associated to this job
		tag = = ET.fromstring(APPS[app_name]).attrib["end_tag"]
		# return True if the end_tag is in stdout, False otherwise
		return tag in stdout
	else: return True

def get_file_path(job_dir, file_path, is_raw_input):
	if is_raw_input: return f"{job_dir}/{os.path.basename(file_path)}"
	else: return utils.DATA_DIR + "/" + os.path.basename(file_path)

#def input_file_exists(job_dir, file, is_raw_input):
#	file_path = get_file_path(job_dir, file, is_raw_input)
#	if not os.path.isfile(file_path) and not os.path.isdir(file_path):
#		logger.debug(f"Expected file '{file_path}' is missing")
#		return False
#	else: return True

def get_all_files_in_settings(job_dir, app_name, settings):
	files = []
	# get the list of keys from the xml that match an input file
	for param in ET.fromstring(APPS[app_name]).findall(".//param"):
		key = param.get("name")
		type = param.get("type")
		is_raw_input = param.get("is_raw_input")
		# search in the settings if the key exists
		if key in settings:
			# if so get the file or list of files
			if type == "folder-list" or type == "file-list":
				for file in settings[key]:
					files.append(get_file_path(job_dir, file, is_raw_input))
			#elif type == "file":
			#	files.append(get_file_path(job_dir, settings[key], is_raw_input))
	return files

def are_all_files_transfered(job_dir, app_name, settings):
	#if os.path.isfile(f"{job_dir}/{FINAL_FILE}"):
	#	if app_name == "diann_1.8.1": return diann181.check_input_files(settings, job_dir, utils.DATA_DIR)
	#	elif app_name == "diann_1.9.1": return diann191.check_input_files(settings, job_dir, utils.DATA_DIR)
	#	elif app_name == "test": return test.check_input_files(settings, job_dir, utils.DATA_DIR)
	#else: logger.debug(f"{job_dir} is still expecting files, {FINAL_FILE} is not there yet...")
	#return False
	if os.path.isfile(f"{job_dir}/{FINAL_FILE}") and app_name in APPS:
		# search in the settings if the key exists, if so get the file or list of files
		for file in get_all_files_in_settings(job_dir, app_name, settings):
			if not os.path.isfile(file) and not os.path.isdir(file):
				logger.debug(f"Expected file '{file}' is missing")
				return False
		# return True if they all exist, False otherwise
		return True
	# return False if the final file is not there yet
	else: return False

def replace_in_command(command, tag, value):
	if tag in command: return command.replace(tag, value)
	else: return command

def get_command_line(app_name, job_dir, settings, nb_cpu, output_dir):
	cmd = []
	if app_name in APPS:
		root = ET.fromstring(APPS[app_name])
		cmd.append(root.attrib["command"])
		for param in root.findall(".//param"):
			key = param.get("name")
			# get the command if the name is in the settings
			if key in settings: 
				command = param.get("command")
				if param.get("type") == "select":
					# TODO search in options
				elif param.get("type") == "range":
					#if "%value%" in command: command = command.replace("%value%", settings[key][0])
					#if "%value2%" in command: command = command.replace("%value2%", settings[key][1])
					command = replace_in_command(command, "%value%", settings[key][0])
					command = replace_in_command(command, "%value2%", settings[key][1])
				elif param.get("type") == "file-list" or param.get("type") == "folder-list":
					repeated_command = param.find("repeated_command")
					if repeated_command is None:
						command = replace_in_command(command, "%value%", settings[key])
					else: 
						for file in settings[key]:
							command += " " + replace_in_command(repeated_command, "%value%", get_file_path(job_dir, file, param.get("is_raw_input")))
				else:
					#if "%value%" in command: command = command.replace("%value%", settings[key])
					command = replace_in_command(command, "%value%", settings[key])
				cmd.append(command)
		# create the full command line as text
		command_line = " ".join(cmd)
		# replace some final variables eventually (at the moment, the only variables allowed are: nb_threads and output_dir, value, value2)
		command_line = command_line.replace("%nb_threads%", f"{nb_cpu}")
		command_line = command_line.replace("%output_dir%", output_dir)
	# return the command line
	return command_line

def generate_script(job_id, job_dir, app_name, settings, host):
	# the working directory is the job directory
	content = f"cd '{job_dir}'\n"
	# create a directory where the output files should be generated
	#output_dir = "./output"
	output_dir = f"./{OUTPUT_DIR}"
	content += f"mkdir '{output_dir}'\n"
	# the script then must call the proper command line
	#cmd = "sleep 60"
	#if app_name == "diann_1.8.1": cmd = diann181.get_command_line(settings, utils.DATA_DIR, host.cpu, output_dir)
	#elif app_name == "diann_1.9.1": cmd = diann191.get_command_line(settings, utils.DATA_DIR, host.cpu, output_dir)
	#elif app_name == "test": cmd = test.get_command_line(settings, utils.DATA_DIR, output_dir)
	# generate the command line based on the xml file and the given settings
	cmd = get_command_line(app_name, job_dir, settings, host.cpu, output_dir)
	# make sure the command ends with the log redirection and the ampersand
	if "1>" not in cmd: cmd += f" 1> {utils.get_stdout_file_name(app_name)}"
	if "2>" not in cmd: cmd += f" 2> {utils.get_stderr_file_name(app_name)}"
	# use a single & to put the command in background and directly store the pid
	content += cmd + " & echo $! > .cumulus.pid\n"
	# write the script in the job directory and return the file
	cmd_file = job_dir + "/.cumulus.cmd"
	utils.write_file(cmd_file, content)
	return cmd_file

def is_file_required(app_name, settings, file):
	#if app_name == "diann_1.8.1": return diann181.is_file_required(settings, file)
	#elif app_name == "diann_1.9.1": return diann191.is_file_required(settings, file)
	#elif app_name == "test": return test.is_file_required(settings, file)
	#else: return False
	# search in the settings for each input file
	for input_file in get_all_files_in_settings(job_dir, app_name, settings):
		# return True if the searched file name is one of the files in the settings
		if os.path.basename(file) == os.path.basename(input_file): return True
	# return False in any other case
	return False

def search_file(app_name, settings, file_tag):
	#if app_name == "diann_1.8.1": return diann181.search_file(settings, file_tag)
	#elif app_name == "diann_1.9.1": return diann191.search_file(settings, file_tag)
	#elif app_name == "test": return test.search_file(settings, file_tag)
	#else: return False
	# search in the settings for each input file
	for input_file in get_all_files_in_settings(job_dir, app_name, settings):
		# return True if the searched file tag is included in one of the files in the settings
		if file_tag in os.path.basename(input_file): return True
	# return False in any other case
	return False
