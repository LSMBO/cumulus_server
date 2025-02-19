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

import logging
import os
import re
import xml.etree.ElementTree as ET

import cumulus_server.libs.cumulus_config as config
import cumulus_server.libs.cumulus_utils as utils

logger = logging.getLogger(__name__)
FINAL_FILE = config.get("final.file")
OUTPUT_DIR = config.get("output.folder")
APPS = {}

def get_app_list(dir_name = "apps"):
	for f in os.listdir(dir_name):
		# add the path to the file
		f = f"apps/{f}"
		if f.endswith(".xml"):
			root = ET.parse(f).getroot()
			# store the link between the id of the app and the content of the file
			id = root.attrib["id"]
			# get the xml content
			with open(f, 'r') as xml:
				APPS[id] = xml.read()
	return APPS

def is_finished(app_name, stdout):
	logger.debug(f"is_finished({app_name}, stdout)")
	if app_name in APPS:
		# extract the end tag from the app xml file associated to this job
		tag = ET.fromstring(APPS[app_name]).attrib["end_tag"]
		# return True if the end_tag is in stdout, False otherwise
		is_tag_found = re.search(tag, stdout) != None
		# logger.debug(tag)
		logger.debug(f"is_finished => {is_tag_found}")
		return is_tag_found
	else: return True

def get_file_path(job_dir, file_path, is_raw_input):
	if is_raw_input == "true": return config.DATA_DIR + "/" + os.path.basename(file_path)
	else: return f"{job_dir}/{os.path.basename(file_path)}"

def get_all_files_to_convert_to_mzml(job_dir, app_name, settings):
	files = []
	# get the list of keys from the xml that match an input file
	if app_name in APPS:
		for param in ET.fromstring(APPS[app_name]).findall(".//filelist"):
			key = param.get("name")
			is_raw_input = param.get("is_raw_input")
			# search in the settings if the key exists
			if key in settings:
				# get the files as an array
				current_files = settings[key] if param.get("multiple") == "true" else [settings[key]]
				for file in current_files:
					file = get_file_path(job_dir, file, is_raw_input)
					if param.get("convert_to_mzml") != None and param.get("convert_to_mzml") == "true": 
						# do not add the file if it has already been converted
						if not os.path.isfile(file.replace(os.path.splitext(file)[1], f".mzML")): files.append(file)
	return files

def get_all_files_in_settings(job_dir, app_name, settings, include_mzml_converted_files = False):
	files = []
	# get the list of keys from the xml that match an input file
	if app_name in APPS:
		for param in ET.fromstring(APPS[app_name]).findall(".//filelist"):
			key = param.get("name")
			is_raw_input = param.get("is_raw_input")
			# search in the settings if the key exists
			if key in settings:
				# get the files as an array
				current_files = settings[key] if param.get("multiple") == "true" else [settings[key]]
				for file in current_files:
					if file == "": continue
					file = get_file_path(job_dir, file, is_raw_input)
					# if the file is marked as to be converted, add the converted file instead
					if include_mzml_converted_files and param.get("convert_to_mzml") != None and param.get("convert_to_mzml") == "true": file = file.replace(os.path.splitext(file)[1], f".mzML")
					# add the file to the list
					files.append(file)
	return files

def are_all_files_transfered(job_dir, app_name, settings):
	if os.path.isfile(f"{job_dir}/{FINAL_FILE}") and app_name in APPS:
		# search in the settings if the key exists, if so get the file or list of files
		for file in get_all_files_in_settings(job_dir, app_name, settings):
			if not os.path.isfile(file) and not os.path.isdir(file):
				logger.debug(f"Expected file '{file}' is missing")
				return False
		# return True if they all exist, False otherwise
		return True
	# return False if the final file is not there yet
	else: 
		logger.debug(f"{job_dir}/{FINAL_FILE} is not there yet")
		return False

def replace_in_command(command, tag, value):
	if tag in command: return command.replace(tag, value)
	else: return command

def get_param_command_line(param, settings, job_dir):
	# param is the xml tag from the app definition
	# settings is an dict containing the settings selected by the user
	cmd = []
	key = param.get("name")
	command = param.get("command")
	if param.tag == "select":
		if key in settings:
			value = settings[key]
			# if there is a command associated to the main select (in this case, no variable is expected)
			if command != None: cmd.append(command)
			# get the option with the selected value, add the command if there is one (no variable expected)
			option = param.find(f"option[@value='{value}']")
			if option.get("command") != None: cmd.append(option.get("command"))
	elif param.tag == "checkbox":
		# add the command line if the key is in the settings (if it is, it means that it's checked)
		# no variable is expected there
		if param.get("name") in settings:
			# the user checked the box, add the corresponding command
			if settings[key] and command != None: cmd.append(command)
			# the used unchecked the box, but there is a command for when it's unchecked
			if not settings[key] and param.get("command_if_unchecked") != None: cmd.append(param.get("command_if_unchecked"))
	elif param.tag == "string":
		# add the command line if the key is in the settings, variable %value% can be expected
		if key in settings: cmd.append(replace_in_command(command, "%value%", settings[key]))
	elif param.tag == "number":
		# add the command line if the key is in the settings, variable %value% can be expected
		if key in settings: cmd.append(replace_in_command(command, "%value%", settings[key]))
	elif param.tag == "range":
		# add the command line if the keys for min and max are in the settings, variables %value% and %value2% can be expected
		key_min = param.get("name") + "-min"
		key_max = param.get("name") + "-max"
		if key_min in settings and key_max in settings:
			command = replace_in_command(command, "%value%", settings[key_min])
			command = replace_in_command(command, "%value2%", settings[key_max])
			cmd.append(command)
	elif param.tag == "filelist":
		# this param can be either a single file/folder or a list of file/folder
		if key in settings:
			# add the command if there is one
			is_raw_input = param.get("is_raw_input")
			if command != None: cmd.append(replace_in_command(command, "%value%", settings[key]))
			# it's also possible to have one command per file, even when it only allows one file
			repeated_command = param.get("repeated_command")
			if repeated_command != None:
				# current_files = param.get("multiple") == "true" ? current_files = settings[key] : [settings[key]]
				current_files = settings[key] if param.get("multiple") == "true" else [settings[key]]
				for file in current_files: 
					file = get_file_path(job_dir, file, is_raw_input)
					if param.get("convert_to_mzml") != None and param.get("convert_to_mzml") == "true": file = file.replace(os.path.splitext(file)[1], f".mzML")
					if is_raw_input == "false": file = os.path.basename(file)
					cmd.append(replace_in_command(repeated_command, "%value%", file))
	# if cmd contains None, log the content of cmd
	if None in cmd: logger.error(f"Error in get_param_command_line for key {key}")
	return " ".join(cmd)

def get_command_line(app_name, job_dir, settings, nb_cpu, output_dir):
	cmd = []
	if app_name in APPS:
		# loop through all params in the xml file, if the param name is in the settings then get its command attribute
		root = ET.fromstring(APPS[app_name])
		cmd.append(root.attrib["command"])
		for section in root:
			for child in section:
				# section can contain param or conditional
				if child.tag.lower() == "conditional":
					# conditional contain a param and a series of when
					condition = child[0]
					command = get_param_command_line(condition, settings, job_dir)
					if command != "": cmd.append(command)
					for when in child.findall("when"):
						# check that this when is the selected one
						if when.get('value') == settings[condition.get('name')]:
							for param in when:
								command = get_param_command_line(param, settings, job_dir)
								if command != "": cmd.append(command)
				else:
					command = get_param_command_line(child, settings, job_dir)
					if command != "": cmd.append(command)
	# create the full command line as text
	command_line = " ".join(cmd)
	# replace some final variables eventually (at the moment, the only variables allowed are: nb_threads and output_dir, value, value2)
	command_line = command_line.replace("%nb_threads%", f"{int(nb_cpu) - 1}")
	command_line = command_line.replace("%output_dir%", output_dir)
	# return the full command line
	return command_line

def generate_script_content(job_id, job_dir, app_name, settings, host_cpu):
	# the working directory is the job directory
	content = f"cd '{job_dir}'\n"
	# store the session id (not the pid anymore, sid are better for cancelling jobs)
	content += "SID=$(ps -p $$ --no-headers -o sid)\n"
	content += "echo $SID > .cumulus.pid\n"
	# create a directory where the output files should be generated
	output_dir = f"./{OUTPUT_DIR}"
	content += f"mkdir '{output_dir}'\n"
	# get the log files paths
	stdout = config.get_final_stdout_path(job_id)
	stderr = config.get_final_stderr_path(job_id)
	# convert the input files eventually
	converter = config.get("converter.raw.to.mzml")
	cmd = ""
	# create the stdout and stderr files
	cmd += f"touch {stdout}\n"
	cmd += f"ln -s {stdout} .cumulus.stdout\n"
	cmd += f"touch {stderr}\n"
	cmd += f"ln -s {stderr} .cumulus.stderr\n"
	for file in get_all_files_to_convert_to_mzml(job_dir, app_name, settings):
		cmd += f"mono '{converter}' -i {file}  1>> {stdout} 2>> {stderr}\n"
	# generate the command line based on the xml file and the given settings
	cmd += get_command_line(app_name, job_dir, settings, host_cpu, output_dir)
	# redirect the output to the log directory
	cmd += f" 1>> {stdout}"
	cmd += f" 2>> {stderr}"
	# finalize the content
	content += cmd + "\n"
	# return file path and the content
	return job_dir + "/.cumulus.cmd", content

def is_file_required(job_dir, app_name, settings, file):
	# search in the settings for each input file
	for input_file in get_all_files_in_settings(job_dir, app_name, settings, True):
		# return True if the searched file name is one of the files in the settings
		if os.path.basename(file) == os.path.basename(input_file): return True
	# return False in any other case
	return False

def is_in_required_files(job_dir, app_name, settings, file_tag):
	# search in the settings for each input file
	for input_file in get_all_files_in_settings(job_dir, app_name, settings):
		# return True if the searched file tag is included in one of the files in the settings
		if file_tag in os.path.basename(input_file): return True
	# return False in any other case
	return False

def get_log_file_content(job_id, is_stdout = True):
	content = ""
	# read log file
	log_file = config.get_final_stdout_path(job_id) if is_stdout else config.get_final_stderr_path(job_id)
	if os.path.isfile(log_file):
		f = open(log_file, "r")
		content = f.read()
		f.close()
	# return its content
	return content

def get_stdout_content(job_id): return get_log_file_content(job_id, True)
def get_stderr_content(job_id): return get_log_file_content(job_id, False)

def get_file_list(job_dir):
	# this function will only return files, empty folders will be disregarded
	filelist = []
	if os.path.isdir(job_dir):
		# list all files including sub-directories
		root_path = job_dir + "/"
		for root, _, files in os.walk(root_path):
			# make sure that the file pathes are relative to the root of the job folder
			rel_path = root.replace(root_path, "")
			for f in files:
				# avoid the .cumulus.* files
				if not f.startswith(".cumulus."):
					# return an array of tuples (name|size)
					file = f if rel_path == "" else rel_path + "/" + f
					# logger.debug(f"get_file_list->add({file})")
					filelist.append((file, utils.get_size(root_path + "/" + file)))
	# the user will select the files they want to retrieve
	return filelist
