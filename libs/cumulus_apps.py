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
import re
import xml.etree.ElementTree as ET
import yaml

import libs.cumulus_config as config
import libs.cumulus_utils as utils

logger = logging.getLogger(__name__)
FINAL_FILE = config.get("final.file")
OUTPUT_DIR = config.get("output.folder")
ALLOWED_CONFIG_FORMATS = ['json', 'yaml']
APPS = {}

def get_app_list(dir_name = "apps"):
	for f in os.listdir(dir_name):
		# add the path to the file
		f = f"apps/{f}"
		if f.endswith(".xml"):
			try:
				root = ET.parse(f).getroot()
				# store the link between the id of the app and the content of the file
				id = root.attrib["id"]
				# get the xml content
				with open(f, 'r') as xml:
					APPS[id] = xml.read()
			except Exception as e:
				logger.error(f"Error on [get_app_list], {e.strerror}: {f}")
	return APPS

def is_finished(job_id, app_name):
	logger.debug(f"is_finished({job_id, app_name})")
	if app_name in APPS:
		# get end_tag_location from the xml file, this attribute may be missing
		tag_location = ET.fromstring(APPS[app_name]).attrib.get("end_tag_location")
		# if tag_location is None, use the default value
		file_content = ""
		if tag_location == None: file_content = get_stdout_content(job_id)
		elif tag_location == "%stderr%": file_content = get_stderr_content(job_id)
		elif os.path.isfile(tag_location):
			f = open(tag_location, "r")
			file_content = f.read()
			f.close()
		else: return False
		# extract the end tag from the app xml file associated to this job
		tag = ET.fromstring(APPS[app_name]).attrib["end_tag"]
		# return True if the end_tag is in stdout, False otherwise
		is_tag_found = re.search(tag, file_content) != None
		# logger.debug(tag)
		logger.debug(f"is_finished => {is_tag_found}")
		return is_tag_found
	else: return False

def get_file_path(job_dir, file_path, is_raw_input):
	if is_raw_input == "true": return config.DATA_DIR + "/" + os.path.basename(file_path)
	else: return f"{job_dir}/{os.path.basename(file_path)}"

def get_mzml_file_path(file_path):
	# replace the extension of the file by .mzML and return the path
	return file_path.replace(os.path.splitext(file_path)[1], f".mzML")

def is_mzml_file_already_converted(file_path):
	# replace the extension of the file by .mzML and check if it exists
	return os.path.isfile(get_mzml_file_path(file_path))

def get_filelist_content(job_dir, param, settings, consider_mzml_converted_files = False, only_files_to_convert_to_mzml = False):
	# option 1: consider that raw files have been converted to mzML
	# option 2: only return the files to convert to mzML, exclude the files that have already been converted
	# these two options are mutually exclusive
	files = []
	key = param.get("name")
	is_raw_input = param.get("is_raw_input")
	convert_to_mzml = param.get("convert_to_mzml") != None and param.get("convert_to_mzml") == "true"
	if key in settings:
		# get the files as an array
		current_files = settings[key] if param.get("multiple") == "true" else [settings[key]]
		for file in current_files:
			file = get_file_path(job_dir, file, is_raw_input)
			if only_files_to_convert_to_mzml:
				# if we only want the files to convert to mzML
				# exclude the local files (they are not raw input files)
				# do not consider raw files if they don't have to be converted
				# exclude the files that have already been converted
				if is_raw_input and convert_to_mzml and not is_mzml_file_already_converted(file): files.append(file)
			else:
				# list all the files, either with or without the mzML extension
				if is_raw_input and convert_to_mzml and consider_mzml_converted_files:
					files.append(get_mzml_file_path(file))
				else:
					files.append(file)
	return files

def get_files(job_dir, app_name, settings, consider_mzml_converted_files = False, only_files_to_convert_to_mzml = False):
	files = []
	# reuse the same code as in get_command_line, to avoid considering params from unused conditionals
	if app_name in APPS:
		# loop through all params in the xml file, if the param name is in the settings then get its command attribute
		root = ET.fromstring(APPS[app_name])
		# loop through all params in the xml file, if the param name is in the settings then get its command attribute
		for section in root:
			for child in section:
				# section can contain param or conditional
				if child.tag.lower() == "conditional":
					# conditional contain a param and a series of when
					condition = child[0]
					for when in child.findall("when"):
						# check that this when is the selected one
						if condition.get('name') in settings and when.get('value') == settings[condition.get('name')]:
							for param in when:
								if param.tag == "filelist": files += get_filelist_content(job_dir, param, settings, consider_mzml_converted_files, only_files_to_convert_to_mzml)
				elif child.tag == "filelist": files += get_filelist_content(job_dir, child, settings, consider_mzml_converted_files, only_files_to_convert_to_mzml)
	return files

def are_all_files_transfered(job_dir, app_name, settings):
	if os.path.isfile(f"{job_dir}/{FINAL_FILE}") and app_name in APPS:
		# search in the settings if the key exists, if so get the file or list of files
		# for file in get_all_files_in_settings(job_dir, app_name, settings):
		for file in get_files(job_dir, app_name, settings):
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
	# command is the command line to modify
	# tag is the tag to replace by the value
	if command == None: return ""
	# replace the tag by the value in the command line
	if tag in command: return command.replace(tag, value)
	else: return command

def get_param_command_line(param, settings, job_dir):
	# param is the xml tag from the app definition
	# settings is an dict containing the settings selected by the user
	cmd = []
	key = param.get("name")
	command = param.get("command")
	# attribute 'command' is not mandatory, it can be missing, return "" if it is
	# if command == None: return ""
	# check the type of the param and get the command line accordingly
	if param.tag == "select":
		if key in settings:
			value = settings[key]
			# if there is a command associated to the main select (in this case, no variable is expected)
			if command != None: cmd.append(command)
			# get the option with the selected value, add the command if there is one (no variable expected)
			option = param.find(f"option[@value='{value}']")
			if option != None and option.get("command") != None: cmd.append(option.get("command"))
	elif param.tag == "checklist":
		# settings[key] should be an array
		# TODO this was not tested!!
		if key in settings:
			for item in settings[key]:
				# item is a tuple (key, value), key is the value of the option, value is the command to execute
				# get the command associated to the option if there is one
				option = param.find(f"option[@value='{item[0]}']")
				if option != None and option.get("command") != None: cmd.append(option.get("command"))
			# value = settings[key]
			# # if there is a command associated to the main element (in this case, no variable is expected)
			# if command != None: cmd.append(command)
			# # get all the options with the selected value, add the command if there is one (no variable expected)
			# for option in param.findall(f"option[@value='{value}']"):
			# 	if option != None and option.get("command") != None: cmd.append(option.get("command"))
			# # option = param.find(f"option[@value='{value}']")
			# # if option != None and option.get("command") != None: cmd.append(option.get("command"))
	elif param.tag == "keyvalues":
		if key in settings:
			# if there is a command associated to the main element (in this case, no variable is expected)
			if command != None: cmd.append(command)
			# use the repeated_command for each option if there is one
			repeated_command = param.get("repeated_command")
			if repeated_command != None:
				# settings[key] should be an array of arrays, each array containing a key and a value
				for item in settings[key]:
					key = item[0]
					val = item[1]
					current_cmd = repeated_command
					current_cmd = replace_in_command(current_cmd, "%key%", key)
					current_cmd = replace_in_command(current_cmd, "%value%", val)
					cmd.append(current_cmd)
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
		if key in settings and settings[key] != "": cmd.append(replace_in_command(command, "%value%", settings[key]))
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

def get_param_number(param, value):
	# if value was not defined, return None
	if value == "": return None
	# value is a string representing a number, either int or float
	step = param.get("step")
	# if step is not defined, it's a int
	if step == None: return int(value)
	# if step is defined and contains a dot, it's a float
	elif "." in step: return float(value)
	# if step is defined and does not contain a dot, it's an int
	else: return int(value)

def add_config_to_settings(key, value, config_settings):
	# separate the path by dots
	full_path = key.split(".")
	# make sure that all parts of the path exist in the dict, create them if they don't, unless for the last part which is the key
	current = config_settings
	for i in range(len(full_path) - 1):
		if full_path[i] not in current: current[full_path[i]] = {}
		current = current[full_path[i]]
	# add the value to the dict, the last part of the path is the key
	current[full_path[-1]] = value
	# print(config_settings)

def get_param_config_value(config_settings, format, job_dir, param, settings):
	if format in ALLOWED_CONFIG_FORMATS:
		# if the param is set to be excluded from the config file, skip it
		if param.get("exclude_from_config") != None and param.get("exclude_from_config") == "true": return
		# read the value of the param in the settings
		key = param.get("name")
		value = "" # placeholder
		if param.tag == "select":
			# if key in settings: value = settings[key]
			if key in settings: add_config_to_settings(key, settings[key], config_settings)
		elif param.tag == "checklist":
			# if key in settings: value = settings[key] # should be an array
			if key in settings: add_config_to_settings(key, settings[key], config_settings) # settings[key] should be an array
		elif param.tag == "keyvalues":
			if key in settings:
				value = {}
				# is_list = False
				# if param.get("is_list") != None and param.get("is_list") == "true": is_list = True
				is_list = True if param.get("is_list") != None and param.get("is_list") == "true" else False
				type_of = param.get("type_of") if param.get("type_of") != None else "string"
				# settings[key] should be an array of arrays, each array containing a key and a value
				for item in settings[key]:
					# v can be a single value or a list, and the type of the value can be either integer, float or string
					k = item[0]
					v = item[1]
					if is_list:
						values = []
						for i in range(len(v)):
							if type_of == "float": values.append(float(v[i]))
							elif type_of == "int": values.append(int(v[i]))
							else: values.append(v[i])
						value[k] = values
					else:
						if type_of == "float": value[k] = float(v)
						elif type_of == "int": value[k] = int(v)
						else: value[k] = v
				add_config_to_settings(key, value, config_settings)
		elif param.tag == "checkbox":
			if key in settings: value = True if settings[key] else False
			else: value = False
			add_config_to_settings(key, value, config_settings)
		elif param.tag == "string":
			# if key in settings: value = settings[key]
			if key in settings: 
				# if the value is empty and allow_empty is set to false, don't add it to the config file
				if settings[key] == "" and param.get("allow_empty") != None and param.get("allow_empty") == "false": return
				add_config_to_settings(key, settings[key], config_settings)
		elif param.tag == "number":
			if key in settings: 
				# add_config_to_settings(key, get_param_number(param, settings[key]), config_settings)
				number = get_param_number(param, settings[key])
				if number != None: add_config_to_settings(key, number, config_settings)
		elif param.tag == "range":
			key_min = param.get("name") + "-min"
			key_max = param.get("name") + "-max"
			if key_min in settings and key_max in settings:
				value = [get_param_number(param, settings[key_min]), get_param_number(param, settings[key_max])]
				add_config_to_settings(key, value, config_settings)
		elif param.tag == "filelist":
			if key in settings:
				is_raw_input = param.get("is_raw_input")
				if param.get("multiple") == "true":
					value = []
					for file in settings[key]:
						file = get_file_path(job_dir, file, is_raw_input)
						if param.get("convert_to_mzml") != None and param.get("convert_to_mzml") == "true": file = file.replace(os.path.splitext(file)[1], f".mzML")
						if is_raw_input == "false": file = os.path.basename(file)
						value.append(file)
				else:
					file = get_file_path(job_dir, settings[key], is_raw_input)
					if param.get("convert_to_mzml") != None and param.get("convert_to_mzml") == "true": file = file.replace(os.path.splitext(file)[1], f".mzML")
					if is_raw_input == "false": file = os.path.basename(file)
					value = file
				add_config_to_settings(key, value, config_settings)

def replace_variables(text, nb_cpu, output_dir):
	# replace the variables in the text
	text = text.replace("'%nb_threads%'", "%nb_threads%")
	text = text.replace("\"%nb_threads%\"", "%nb_threads%")
	text = text.replace("%nb_threads%", f"{int(nb_cpu) - 1}")
	text = text.replace("%output_dir%", output_dir)
	#return the text
	return text

def write_config_file(config_file, config_settings, format, nb_cpu, output_dir):
	# convert the settings into text
	text = ""
	if format == "json": text = json.dumps(config_settings)
	elif format == "yaml": text = yaml.dump(config_settings)
	# replace variables in the text
	text = replace_variables(text, nb_cpu, output_dir)
	# write the content of the settings in the file
	with open(config_file, "w") as f:
		f.write(text)

def is_condition_fulfilled(condition, when, settings):
	# the condition has to be in the settings and the value has to match the one in the "when" tag
	if condition.tag == "select" or condition.tag == "string" or condition.tag == "number": 
		if when.get("allow_regex") != None and when.get("allow_regex") == "true":
			# if the condition is a regex, check if the value matches the regex
			return condition.get('name') in settings and re.search(when.get('value'), settings[condition.get('name')])
		else:
			# default behavior, check if the value is equal to the one in the settings
			return condition.get('name') in settings and when.get('value') == settings[condition.get('name')]
	elif condition.tag == "checkbox": 
		if condition.get('name') in settings:
			if settings[condition.get('name')] == True: return when.get('value') == "true"
			else: return when.get('value') == "false"
	# the other tags are not supported yet
	# elif condition.tag == "checklist": return
	# elif condition.tag == "keyvalues": return
	# elif condition.tag == "range": return
	# elif condition.tag == "filelist": return
	return False

def get_command_line(app_name, job_dir, settings, nb_cpu, output_dir):
	cmd = []
	config_format = None
	if app_name in APPS:
		# loop through all params in the xml file, if the param name is in the settings then get its command attribute
		root = ET.fromstring(APPS[app_name])
		# get the value of the attribute 'convert_config_to' if it exists in root
		config_format = root.get("convert_config_to")
		# prepare a dict to store the settings in the format expected by the config file (even if the config file is not used)
		config_settings = {}
		# loop through all params in the xml file, if the param name is in the settings then get its command attribute
		cmd.append(root.attrib["command"])
		for section in root:
			# print(f"App '{app_name}' - Section: {section.get("name")}")
			for child in section:
				# section can contain param or conditional
				if child.tag.lower() == "conditional":
					# conditional contain a param and a series of when
					condition = child[0]
					command = get_param_command_line(condition, settings, job_dir)
					if command != "": cmd.append(command)
					get_param_config_value(config_settings, config_format, job_dir, condition, settings)
					for when in child.findall("when"):
						# check that this when is the selected one
						# if condition.get('name') in settings and when.get('value') == settings[condition.get('name')]:
						if is_condition_fulfilled(condition, when, settings):
							for param in when:
								command = get_param_command_line(param, settings, job_dir)
								if command != "": cmd.append(command)
								# fill config_settings with the param value in the proper path
								get_param_config_value(config_settings, config_format, job_dir, param, settings)
				else:
					command = get_param_command_line(child, settings, job_dir)
					if command != "": cmd.append(command)
					# fill config_settings with the param value in the proper path
					get_param_config_value(config_settings, config_format, job_dir, child, settings)
	# create the full command line as text
	command_line = " ".join(cmd)
	# config_format should be None unless it's in ['json', 'yaml']
	if config_format != None and config_format in ALLOWED_CONFIG_FORMATS:
		# get the file path of the config file
		config_file = f"{job_dir}/.cumulus.settings.{config_format}"
		# write the content of the settings in the file
		write_config_file(config_file, config_settings, config_format, nb_cpu, output_dir)
		# replace the variable in the command line
		command_line = command_line.replace("%config-file%", config_file)
	# replace some final variables eventually (at the moment, the only variables allowed are: nb_threads and output_dir, value, value2)
	command_line = replace_variables(command_line, nb_cpu, output_dir)
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
	# for file in get_all_files_to_convert_to_mzml(job_dir, app_name, settings):
	for file in get_files(job_dir, app_name, settings, False, True):
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
	# for input_file in get_all_files_in_settings(job_dir, app_name, settings, True):
	for input_file in get_files(job_dir, app_name, settings, True):
		# return True if the searched file name is one of the files in the settings
		if os.path.basename(file) == os.path.basename(input_file): return True
	# return False in any other case
	return False

def is_in_required_files(job_dir, app_name, settings, file_tag):
	# search in the settings for each input file
	# for input_file in get_all_files_in_settings(job_dir, app_name, settings):
	for input_file in get_files(job_dir, app_name, settings):
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
