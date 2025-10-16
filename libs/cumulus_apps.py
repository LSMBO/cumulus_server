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
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET
import yaml

import libs.cumulus_config as config
import libs.cumulus_utils as utils

logger = logging.getLogger(__name__)
FINAL_FILE = config.get("final.file")
INPUT_DIR = config.get("input.folder")
OUTPUT_DIR = config.get("output.folder")
ALLOWED_CONFIG_FORMATS = ['json', 'yaml']
APPS = {}
DATE_OF_LAST_APP_UPDATE = ""

def is_there_app_update(dir_name = "apps"):
	"""
	Checks if there is an updated XML app file in the specified directory compared to the last known update date.
	This function allows to reload the app list if there is a new app file in the directory, without restarting the server.

	Args:
		dir_name (str, optional): The directory to search for app XML files. Defaults to "apps", but can be different for testing purposes.

	Returns:
		bool: True if there is at least one XML file in the directory with a modification date more recent than the global DATE_OF_LAST_APP_UPDATE, or if DATE_OF_LAST_APP_UPDATE is not set. False otherwise.

	Note:
		Relies on the global variable DATE_OF_LAST_APP_UPDATE being defined and representing the last update timestamp (as a float or compatible type).
	"""
	# if no date of last update is set, return True
	if DATE_OF_LAST_APP_UPDATE == "": return True
	# list all the files in the apps directory and check if the date of the last update is more recent than the one in the global variable
	for f in os.listdir(dir_name):
		# check if the file is a xml file
		if f.endswith(".xml"):
			# get the date of the last update
			date_of_last_update = os.path.getmtime(f"{dir_name}/{f}")
			# if the date is more recent than the one in the global variable, return True
			if date_of_last_update > DATE_OF_LAST_APP_UPDATE:
				return True
	# if no file is more recent, return False
	return False

def get_app_list(dir_name = "apps"):
	"""
	Scans the specified directory for XML files representing apps, parses each XML file to extract its 'id' attribute,
	and stores the content of each XML file in the global APPS dictionary using the app id as the key.
	Also updates the global DATE_OF_LAST_APP_UPDATE with the current timestamp.

	Args:
		dir_name (str, optional): The directory to scan for app XML files. Defaults to "apps".

	Returns:
		dict: The APPS dictionary mapping app ids to their XML content as strings.

	Side Effects:
		- Modifies the global APPS dictionary.
		- Updates the global DATE_OF_LAST_APP_UPDATE variable.
		- Logs errors encountered during XML parsing or file reading.
	"""
	global DATE_OF_LAST_APP_UPDATE
	# reset the APPS dict
	APPS.clear()
	# get the list of apps in the directory
	for f in os.listdir(dir_name):
		# add the path to the file
		f = f"{dir_name}/{f}"
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
	# store the current time as the date of last app update
	DATE_OF_LAST_APP_UPDATE = time.time()
	# return the list of apps
	return APPS

def is_finished(job_id, app_name):
	"""
	Determines whether a job has finished by searching for a specific end tag in the job's output.

	Args:
		job_id (str): The identifier of the job to check.
		app_name (str): The name of the application associated with the job.

	Returns:
		bool: True if the end tag is found in the appropriate output (stdout, stderr, or a specified file), False otherwise.

	Notes:
		- The function retrieves the end tag and its location from the application's XML configuration.
		- If the end tag location is not specified, it defaults to checking the job's stdout.
		- If the end tag location is "%stderr%", it checks the job's stderr.
		- If a file path is specified and exists, it reads from that file.
		- Returns False if the application is not found or if the end tag location is invalid.
	"""
	logger.debug(f"is_finished({job_id, app_name})")
	if app_name in APPS:
		# get end_tag_location from the xml file, this attribute may be missing
		tag_location = ET.fromstring(APPS[app_name]).attrib.get("end_tag_location")
		# if tag_location is None, use the default value
		file_content = ""
		# if tag_location == None: file_content = get_stdout_content(job_id)
		# elif tag_location == "%stderr%": file_content = get_stderr_content(job_id)
		if tag_location == None or tag_location == "%stderr%": file_content = get_log_file_content(job_id)
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
	"""
	Returns the full file path based on the job directory, file path, and whether the input is raw.

	Args:
		job_dir (str): The directory associated with the job.
		file_path (str): The original file path.
		is_raw_input (str): Indicates if the input is raw ("true" or other). Raw files are in DATA_DIR, other files are in the job folder.

	Returns:
		str: The constructed file path. If is_raw_input is "true", returns the path in the DATA_DIR with the file's basename.
			 Otherwise, returns the path in the job_dir with the file's basename.
	
	Notes:
		Raw/Fasta tags will be replaced by Shared/Local in the future.
		This function does not check if the file exists, it just returns the path the file should have.
	"""
	if is_raw_input == "true": return config.DATA_DIR + "/" + os.path.basename(file_path)
	# else: return f"{job_dir}/{os.path.basename(file_path)}"
	else: return f"{job_dir}/{INPUT_DIR}/{os.path.basename(file_path)}"

def is_mzml_file_already_converted(file_path):
	"""
	Checks if the mzML version of the given file already exists.

	Args:
		file_path (str): The path to the original file.

	Returns:
		bool: True if the corresponding .mzML file exists, False otherwise.
	"""
	# replace the extension of the file by .mzML and check if it exists
	return os.path.isfile(utils.get_mzml_file_path(file_path))

def get_filelist_content(job_dir, param, settings, consider_mzml_converted_files = False, only_files_to_convert_to_mzml = False):
	"""
	Retrieve a list of file paths based on job parameters and settings, with options to filter or convert files.

	Args:
		job_dir (str): The base directory for job files.
		param (dict): Parameter dictionary containing file selection options. Expected keys include:
			- "name" (str): The key to look up in settings for file(s).
			- "is_raw_input" (bool): Whether the files are raw input files.
			- "convert_to_mzml" (str or None): If "true", indicates files should be converted to mzML.
			- "multiple" (str): If "true", multiple files are expected.
		settings (dict): Dictionary mapping parameter names to file paths or lists of file paths.
		consider_mzml_converted_files (bool, optional): If True, return mzML-converted file paths instead of raw files. Default is False.
		only_files_to_convert_to_mzml (bool, optional): If True, return only files that need to be converted to mzML (i.e., exclude already converted files). Default is False.

	Returns:
		list: List of file paths, filtered and/or converted according to the provided options.

	Notes:
		- The options `consider_mzml_converted_files` and `only_files_to_convert_to_mzml` are mutually exclusive.
		- Helper functions used: `get_file_path`, `is_mzml_file_already_converted`, `get_mzml_file_path`.
	"""
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
					files.append(utils.get_mzml_file_path(file))
				else:
					files.append(file)
	return files

def get_files(job_dir, app_name, settings, consider_mzml_converted_files = False, only_files_to_convert_to_mzml = False):
	"""
	Retrieve a list of files based on application parameters and user settings.

	This function parses the XML definition of an application to determine which files should be considered,
	based on the provided settings. It supports handling of conditional parameters and file lists, and can
	optionally filter files related to mzML conversion.

	Args:
		job_dir (str): The directory where job files are located.
		app_name (str): The name of the application whose parameters are being processed.
		settings (dict): A dictionary of parameter names and their selected values.
		consider_mzml_converted_files (bool, optional): If True, include files that have already been converted to mzML. Defaults to False.
		only_files_to_convert_to_mzml (bool, optional): If True, include only files that need to be converted to mzML. Defaults to False.

	Returns:
		list: A list of file paths that match the specified criteria and application settings.
	"""
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

def are_all_files_transfered(job_dir, app_name, settings, consider_mzml_converted_files = False):
	"""
	Checks whether all expected files for a given job and application have been transferred.

	This function verifies that a final file exists in the specified job directory and that the application name is valid.
	It then checks if all files (or directories) expected for the job, as determined by the application settings, are present.

	Args:
		job_dir (str): The directory path of the job.
		app_name (str): The name of the application.
		settings (dict): The settings dictionary containing expected files for each application.

	Returns:
		bool: True if all expected files (or directories) exist, including the final file, False otherwise.
	"""
	if os.path.isfile(f"{job_dir}/{FINAL_FILE}") and app_name in APPS:
		# search in the settings if the key exists, if so get the file or list of files
		# for file in get_all_files_in_settings(job_dir, app_name, settings):
		for file in get_files(job_dir, app_name, settings, consider_mzml_converted_files):
			if not os.path.isfile(file) and not os.path.isdir(file):
				logger.debug(f"Expected file '{file}' is missing")
				return False
		# return True if they all exist, False otherwise
		return True
	# return False if the final file is not there yet
	else: 
		logger.debug(f"{job_dir}/{FINAL_FILE} is not there yet")
		return False

def link_shared_files(job_dir, app_name, settings):
	logger.info("Linking data to the job directory")
	dest_path = Path(f"{job_dir}/{INPUT_DIR}").resolve()
	for file in get_files(job_dir, app_name, settings, True): # get files after mzML conversion
		file_path = Path(file).resolve()
		link_name = dest_path / file_path.name
		if not link_name.exists(): link_name.symlink_to(file_path)

def replace_in_command(command, tag, value):
	"""
	Replaces a specified tag in a command string with a given value.

	Args:
		command (str): The command line string to modify.
		tag (str): The substring (tag) to be replaced in the command.
		value (str): The value to replace the tag with.

	Returns:
		str: The modified command string with the tag replaced by the value.
			 Returns an empty string if the command is None.
			 If the tag is not found in the command, returns the original command.
	"""
	# command is the command line to modify
	# tag is the tag to replace by the value
	if command == None: return ""
	# replace the tag by the value in the command line
	if tag in command: return command.replace(tag, value)
	else: return command

def get_param_command_line(param, settings, job_dir):
	"""
	Generates a command line string based on an XML parameter definition, user-selected settings, and a job directory.

	This function interprets various types of parameter XML tags (such as "select", "checklist", "keyvalues", "checkbox", "string", "number", "range", and "filelist"),
	and constructs the appropriate command line arguments by extracting values from the provided settings dictionary and formatting commands as specified in the XML.

	Args:
		param (xml.etree.ElementTree.Element): The XML element representing the parameter definition. The tag and attributes of this element determine how the command is constructed.
		settings (dict): A dictionary containing user-selected values for each parameter, keyed by parameter name.
		job_dir (str): The directory path for the current job, used for resolving file paths.

	Returns:
		str: The constructed command line string for the given parameter and settings.

	Notes:
		- The function supports multiple parameter types, each with its own logic for extracting and formatting command line arguments.
		- If a command or repeated_command attribute is missing where expected, the function handles it gracefully.
		- If any part of the command construction results in a None value, an error is logged.
	"""
	# param is the xml tag from the app definition
	# settings is an dict containing the settings selected by the user
	cmd = []
	key = param.get("name")
	command = param.get("command")
	# attribute 'command' is not mandatory, it can be missing, return "" if it is
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
		if key in settings:
			for item in settings[key]:
				# item is a tuple (key, value), key is the value of the option, value is the command to execute
				# get the command associated to the option if there is one
				option = param.find(f"option[@value='{item[0]}']")
				if option != None and option.get("command") != None: cmd.append(option.get("command"))
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
			# is_raw_input = param.get("is_raw_input")
			if command != None: cmd.append(replace_in_command(command, "%value%", settings[key]))
			# it's also possible to have one command per file, even when it only allows one file
			repeated_command = param.get("repeated_command")
			if repeated_command != None:
				# current_files = param.get("multiple") == "true" ? current_files = settings[key] : [settings[key]]
				current_files = settings[key] if param.get("multiple") == "true" else [settings[key]]
				for file in current_files: 
					# file = get_file_path(job_dir, file, is_raw_input)
					file = get_file_path(job_dir, file, False) # all files should be in the job/input folder, raw files should have a symlink there
					if param.get("convert_to_mzml") != None and param.get("convert_to_mzml") == "true": file = file.replace(os.path.splitext(file)[1], f".mzML")
					cmd.append(replace_in_command(repeated_command, "%value%", file))
	# if cmd contains None, log the content of cmd
	if None in cmd: logger.error(f"Error in get_param_command_line for key {key}")
	return " ".join(cmd)

def get_param_number(param, value):
	"""
	Take a "number" Parameter from the XML app file and returns its value as as integer or a float.

	Args:
		param (dict): A dictionary that may contain a 'step' key indicating the numeric type.
		value (str): The string representation of the number to convert.

	Returns:
		int or float or None: The converted number as int or float, or None if value is an empty string.

	Notes:
		- If 'step' is not defined in param, the value is converted to int.
		- If 'step' contains a dot ('.'), the value is converted to float.
		- If 'step' does not contain a dot, the value is converted to int.
	"""
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
	"""
	Adds a configuration value to a nested dictionary structure based on a dot-separated key path.

	Args:
		key (str): Dot-separated string representing the path where the value should be inserted (e.g., "database.host").
		value (Any): The value to insert at the specified path.
		config_settings (dict): The dictionary to update with the new configuration value.

	Modifies:
		config_settings (dict): Updates the dictionary in-place, creating nested dictionaries as needed.

	Example:
		config = {}
		add_config_to_settings("database.host", "localhost", config)
		# Result: config == {"database": {"host": "localhost"}}
	"""
	# separate the path by dots
	full_path = key.split(".")
	# make sure that all parts of the path exist in the dict, create them if they don't, unless for the last part which is the key
	current = config_settings
	for i in range(len(full_path) - 1):
		if full_path[i] not in current: current[full_path[i]] = {}
		current = current[full_path[i]]
	# add the value to the dict, the last part of the path is the key (unless if the key is "_", this allows the creation of parents without children)
	if full_path[-1] != "_": current[full_path[-1]] = value
	# print(config_settings)

def get_param_config_value(config_settings, format, job_dir, param, settings):
	"""
	Processes a parameter definition and its corresponding value from user settings, 
	and adds the appropriate configuration entry to the config_settings dictionary 
	based on the parameter's type and attributes.

	Parameters:
		config_settings (dict): The dictionary to which the processed configuration values are added.
		format (str): The configuration format (must be in ALLOWED_CONFIG_FORMATS).
		job_dir (str): The directory path for job-related files, used for resolving file paths.
		param (Element or dict): The parameter definition, typically an XML element or dict with attributes.
		settings (dict): The user-provided settings containing parameter values.

	Behavior:
		- Skips parameters marked as excluded from the config.
		- Handles different parameter types (select, checklist, keyvalues, checkbox, string, number, range, filelist).
		- Converts and validates values as needed (e.g., type casting, handling empty values, file path resolution).
		- Adds the processed value to config_settings using add_config_to_settings.

	Returns:
		None
	"""
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
			# if key in settings: value = True if settings[key] else False
			# else: value = False
			# add_config_to_settings(key, value, config_settings)
			if key in settings:
				value = True if settings[key] else False
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
				# is_raw_input = param.get("is_raw_input")
				if param.get("multiple") == "true":
					value = []
					for file in settings[key]:
						# file = get_file_path(job_dir, file, is_raw_input)
						file = get_file_path(job_dir, file, False) # all files should be in the job/input folder, raw files should have a symlink there
						if param.get("convert_to_mzml") != None and param.get("convert_to_mzml") == "true": file = file.replace(os.path.splitext(file)[1], f".mzML")
						value.append(file)
				else:
					# file = get_file_path(job_dir, settings[key], is_raw_input)
					file = get_file_path(job_dir, settings[key], False) # all files should be in the job/input folder, raw files should have a symlink there
					if param.get("convert_to_mzml") != None and param.get("convert_to_mzml") == "true": file = file.replace(os.path.splitext(file)[1], f".mzML")
					value = file
				add_config_to_settings(key, value, config_settings)

def replace_variables(text, nb_cpu, input_dir, output_dir):
	"""
	Replaces specific placeholder variables in the given text with provided values.

	This function searches for occurrences of the '%nb_threads%' and '%output_dir%' placeholders
	in the input text and replaces them with the appropriate values:
	- '%nb_threads%' is replaced with the number of CPUs minus one.
	- '%output_dir%' is replaced with the specified output directory.

	Additionally, it normalizes any instances of '%nb_threads%' that are enclosed in single or double quotes.

	Args:
		text (str): The input string containing placeholders to be replaced.
		nb_cpu (int): The total number of CPUs; used to compute the value for '%nb_threads%'.
		output_dir (str): The directory path to replace '%output_dir%' in the text.

	Returns:
		str: The text with all placeholders replaced by their corresponding values.
	"""
	# replace the variables in the text
	text = text.replace("'%nb_threads%'", "%nb_threads%")
	text = text.replace("\"%nb_threads%\"", "%nb_threads%")
	text = text.replace("%nb_threads%", f"{int(nb_cpu) - 1}")
	text = text.replace("%input_dir%", input_dir)
	text = text.replace("%output_dir%", output_dir)
	#return the text
	return text

def write_config_file(config_file, config_settings, format, nb_cpu, input_dir, output_dir):
	"""
	Writes configuration settings to a file in the specified format after replacing variables.

	Args:
		config_file (str): Path to the configuration file to write.
		config_settings (dict): Dictionary containing configuration settings.
		format (str): Format to serialize the settings ('json' or 'yaml').
		nb_cpu (int): Number of CPUs to be used for variable replacement.
		output_dir (str): Output directory to be used for variable replacement.

	Raises:
		ValueError: If the specified format is not supported.
		IOError: If there is an error writing to the file.

	Note:
		The function assumes that `replace_variables`, `json`, and `yaml` are available in the scope.
	"""
	# convert the settings into text
	text = ""
	if format == "json": text = json.dumps(config_settings)
	elif format == "yaml": text = yaml.dump(config_settings)
	# replace variables in the text
	text = replace_variables(text, nb_cpu, input_dir, output_dir)
	# write the content of the settings in the file
	with open(config_file, "w") as f:
		f.write(text)

def is_condition_fulfilled(condition, when, settings):
	"""
	Checks if a given condition is fulfilled based on the provided settings and criteria.
	XML apps can define conditions that must be met for certain actions to be executed.
	It is necessary to evaluate these conditions against the current settings to avoid using parameters that have not been selected.

	Args:
		condition (xml.etree.ElementTree.Element): The XML element representing the condition to check. 
			Supported tags: "select", "string", "number", "checkbox".
		when (dict): A dictionary containing criteria for the condition, such as 'value' and optional 'allow_regex'.
		settings (dict): A dictionary of current settings to evaluate the condition against.

	Returns:
		bool: True if the condition is fulfilled according to the criteria in 'when' and the values in 'settings', False otherwise.

	Notes:
		- For "select", "string", and "number" tags, supports both direct value comparison and regex matching (if 'allow_regex' is set to "true").
		- For "checkbox" tag, checks if the setting is True or False and compares it to the expected value in 'when'.
		- Other tags are not currently supported and will return False.
	"""
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

def get_command_line(app_name, job_dir, settings, nb_cpu, input_dir, output_dir):
	"""
	Generates the command line string for executing a specified application with given settings.

	This function parses the application's XML configuration, constructs the command line by processing
	parameters and conditionals, and optionally generates a configuration file (JSON or YAML) if required.
	It replaces placeholders in the command line with actual values such as the number of CPUs and output directory.

	Args:
		app_name (str): The name of the application to run.
		job_dir (str): The directory where the job is executed and where config files may be written.
		settings (dict): A dictionary of parameter names and their values to be used for the application.
		nb_cpu (int): The number of CPUs (threads) to be used by the application.
		output_dir (str): The directory where output files should be written.

	Returns:
		str: The complete command line string ready to be executed.

	Raises:
		KeyError: If the application name is not found in the APPS dictionary.
		ET.ParseError: If the application's XML configuration is invalid.
	"""
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
		write_config_file(config_file, config_settings, config_format, nb_cpu, input_dir, output_dir)
		# replace the variable in the command line
		command_line = command_line.replace("%config-file%", config_file)
	# replace some final variables eventually (at the moment, the only variables allowed are: nb_threads and output_dir, value, value2)
	command_line = replace_variables(command_line, nb_cpu, input_dir, output_dir)
	# return the full command line
	return command_line

def generate_script_content(job_id, job_dir, app_name, settings, host_cpu):
	"""
	Generates the content of a shell script to execute a job in a specified directory, 
	output directory creation, and logging.

	Args:
		job_id (str): Unique identifier for the job.
		job_dir (str): Path to the job's working directory.
		app_name (str): Name of the application to run.
		settings (dict): Dictionary of settings for the job/application.
		host_cpu (str): Host CPU information for resource allocation.

	Returns:
		tuple: A tuple containing:
			- str: The path to the generated script file (e.g., "<job_dir>/.cumulus.cmd").
			- str: The content of the shell script to be executed.
	
	Notes:
		- The script sets up the working directory, manages session IDs, creates output and log files, 
		  and converts input files as needed using appropriate converters.
		- The script command line is generated based on the application, job directory, settings, and CPU.
		- Output and error logs are redirected to specified log files.
	"""
	# create a directory where the output files should be generated
	input_dir = f"./{INPUT_DIR}"
	output_dir = f"./{OUTPUT_DIR}"
	# generate the command line based on the xml file and the given settings
	cmd = get_command_line(app_name, job_dir, settings, host_cpu, input_dir, output_dir)
	# return file path and the content
	return job_dir + "/.cumulus.cmd", cmd

def is_file_required(job_dir, app_name, settings, file):
	"""
	Determines whether a given file is required based on the application's settings.
	This function is called when checking if a file can be deleted (because too old) or if it is still needed for a job.

	Args:
		job_dir (str): The directory of the job.
		app_name (str): The name of the application.
		settings (dict): The settings dictionary containing file information.
		file (str): The path to the file to check.

	Returns:
		bool: True if the file is required according to the settings, False otherwise.
	"""
	# search in the settings for each input file
	# for input_file in get_all_files_in_settings(job_dir, app_name, settings, True):
	for input_file in get_files(job_dir, app_name, settings, True):
		# return True if the searched file name is one of the files in the settings
		if os.path.basename(file) == os.path.basename(input_file): return True
	# return False in any other case
	return False

def is_in_required_files(job_dir, app_name, settings, file_tag):
	"""
	Checks if a file with a specific tag exists among the required input files for a given application.
	This function is called when checking if a file can be deleted (because too old) or if it is still needed for a job.

	Args:
		job_dir (str): The directory where the job files are located.
		app_name (str): The name of the application.
		settings (dict): The settings dictionary containing file information.
		file_tag (str): The tag to search for in the input file names.

	Returns:
		bool: True if a file with the specified tag is found among the required files, False otherwise.
	"""
	# search in the settings for each input file
	# for input_file in get_all_files_in_settings(job_dir, app_name, settings):
	for input_file in get_files(job_dir, app_name, settings):
		# return True if the searched file tag is included in one of the files in the settings
		if file_tag in os.path.basename(input_file): return True
	# return False in any other case
	return False

# def get_log_file_content(job_id, is_stdout = True):
def get_log_file_content(job_id):
	"""
	Retrieve the content of a job's log file (stdout or stderr).

	Args:
		job_id (str): The unique identifier of the job whose log file is to be read.
		is_stdout (bool, optional): If True, reads the standard output log file; 
			if False, reads the standard error log file. Defaults to True.

	Returns:
		str: The content of the specified log file as a string. Returns an empty string if the file does not exist.
	"""
	content = ""
	# read log file
	# log_file = utils.get_log_file_path(job_id, is_stdout)
	log_file = utils.get_log_file_path(job_id)
	if os.path.isfile(log_file):
		f = open(log_file, "r")
		content = f.read()
		f.close()
	# return its content
	return content

# def get_stdout_content(job_id): return get_log_file_content(job_id, True)
# def get_stderr_content(job_id): return get_log_file_content(job_id, False)

def get_file_list(job_dir):
	"""
	Recursively retrieves a list of files from the specified job directory, excluding empty folders and files starting with '.cumulus.'.

	Args:
		job_dir (str): The path to the root job directory.

	Returns:
		list of tuple: A list of tuples, each containing the relative file path (str) and its size (int, in bytes).
	"""
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

def get_output_file_list(job_dir):
	"""
	Recursively retrieves a list of files from the output folder of the specified job directory.
	Folders are not returned, they will be retrieved from the files pathes that are returned.

	Args:
		job_dir (str): The path to the root job directory.

	Returns:
		list of tuple: A list of tuples, each containing the relative file path (str) and its size (int, in bytes).
	"""
	# this function will only return files, empty folders will be disregarded
	filelist = []
	root_path = job_dir + "/" + OUTPUT_DIR + "/"
	if os.path.isdir(root_path):
		# list all files including sub-directories
		for root, _, files in os.walk(root_path):
			# make sure that the file pathes are relative to the root of the job folder
			rel_path = root.replace(root_path, "")
			for f in files:
				# return an array of tuples (name|size)
				file = f if rel_path == "" else rel_path + "/" + f
				# logger.debug(f"get_output_file_list->add({file})")
				filelist.append((file, utils.get_size(root_path + "/" + file)))
	# the user will select the files they want to retrieve
	return filelist
