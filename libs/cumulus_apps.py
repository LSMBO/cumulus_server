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

logger = logging.getLogger(__name__)
FINAL_FILE = config.get("final.file")
OUTPUT_DIR = config.get("output.folder")
APPS = {}

def get_app_list():
	app_list = []
	for f in os.listdir("apps"):
		# add the path to the file
		f = f"apps/{f}"
		if f.endswith(".xml"):
			root = ET.parse(f).getroot()
			# store the link between the id of the app and the content of the file
			id = root.attrib["id"]
			# do not return the app if it's tagged as hidden (probably an old version)
			hidden = root.get("hidden")
			if hidden is None or hidden == "false":
				# get the xml content
				with open(f, 'r') as xml:
					APPS[id] = xml.read()
	return APPS

def is_finished(app_name, stdout):
	if app_name in APPS:
		# extract the end tag from the app xml file associated to this job
		tag = ET.fromstring(APPS[app_name]).attrib["end_tag"]
		# return True if the end_tag is in stdout, False otherwise
		return tag in stdout
	else: return True

def get_file_path(job_dir, file_path, is_raw_input):
	if is_raw_input == "true": return utils.DATA_DIR + "/" + os.path.basename(file_path)
	else: return f"{job_dir}/{os.path.basename(file_path)}"
	# else: return os.path.basename(file_path)

def get_all_files_to_convert_to_mzml(job_dir, app_name, settings):
	files = []
	# get the list of keys from the xml that match an input file
	for param in ET.fromstring(APPS[app_name]).findall(".//filelist"):
		key = param.get("name")
		is_raw_input = param.get("is_raw_input")
		# search in the settings if the key exists
		if key in settings:
			# get the files as an array
			#current_files = param.get("multiple") == "true" ? current_files = settings[key] : [settings[key]]
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
	for param in ET.fromstring(APPS[app_name]).findall(".//filelist"):
		key = param.get("name")
		is_raw_input = param.get("is_raw_input")
		# search in the settings if the key exists
		if key in settings:
			# get the files as an array
			# current_files = param.get("multiple") == "true" ? current_files = settings[key] : [settings[key]]
			current_files = settings[key] if param.get("multiple") == "true" else [settings[key]]
			for file in current_files:
				file = get_file_path(job_dir, file, is_raw_input)
				# if the file is marked as to be converted, add the converted file instead
				if include_mzml_converted_files and param.get("convert_to_mzml") != None and param.get("convert_to_mzml") == "true": file = file.replace(os.path.splitext(file)[1], f".mzML")
				# add the file to the list
				files.append(file)
	joined_files = "\n- ".join(files)
	logger.debug(f"get_all_files_in_settings({job_dir}):\n- {joined_files}")
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

def check_conditional(xml, param_name, settings):
	# search for a <conditional> in the parents
	# if there is one
		# get the only param from the children of the conditional
		# get its name from xml and value from settings
		# search for the first parent that is a <when>
		# compare when.value and settings.name
		# return True if they math, otherwise False
	# else return True
	return True

def get_param_command_line(param, settings, job_dir):
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
		if param.get("name") in settings: cmd.append(command)
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
	return " ".join(cmd)

def get_command_line(app_name, job_dir, settings, nb_cpu, output_dir):
	cmd = []
	if app_name in APPS:
		# loop through all params in the xml file, if the param name is in the settings then get its command attribute
		root = ET.fromstring(APPS[app_name])
		cmd.append(root.attrib["command"])
		for section in root:
			# print(f"\t{section.tag} {section.get('name')}")
			for child in section:
				# section can contain param or conditional
				if child.tag.lower() == "conditional":
					# conditional contain a param and a series of when
					condition = child[0]
					command = get_param_command_line(condition, settings, job_dir)
					if command != "": cmd.append(command)
					#print(f"\t\t{condition.tag} {condition.get('name')}")
					for when in child.findall("when"):
						#print(f"\t\twhen value='{when.get('value')}'")
						# check that this when is the selected one
						if when.get('value') == settings[condition.get('name')]:
							for param in when:
								#print(f"\t\t\t{param.tag} {param.get('name')}")
								command = get_param_command_line(param, settings, job_dir)
								if command != "": cmd.append(command)
				else:
					#print(f"\t\t{child.tag} {child.get('name')}")
					command = get_param_command_line(param, settings, job_dir)
					if command != "": cmd.append(command)

	
	# create the full command line as text
	command_line = " ".join(cmd)
	# replace some final variables eventually (at the moment, the only variables allowed are: nb_threads and output_dir, value, value2)
	command_line = command_line.replace("%nb_threads%", f"{nb_cpu}")
	command_line = command_line.replace("%output_dir%", output_dir)
	# return the full command line
	return command_line

def generate_script(job_id, job_dir, app_name, settings, host):
	# the working directory is the job directory
	content = f"cd '{job_dir}'\n"
	# create a directory where the output files should be generated
	output_dir = f"./{OUTPUT_DIR}"
	content += f"mkdir '{output_dir}'\n"
	# get the log files paths
	stdout = utils.get_final_stdout_path(job_id)
	stderr = utils.get_final_stderr_path(job_id)
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
	cmd += get_command_line(app_name, job_dir, settings, host.cpu, output_dir)
	# redirect the output to the log directory
	cmd += f" 1>> {stdout}"
	cmd += f" 2>> {stderr}"
	# use a single & to put the command in background and directly store the pid
	# content += cmd + " & echo $! > .cumulus.pid\n"
	content += cmd + "\n"
	# write the script in the job directory and return the file
	cmd_file = job_dir + "/.cumulus.cmd"
	utils.write_file(cmd_file, content)
	return cmd_file

def is_file_required(job_dir, app_name, settings, file):
	# search in the settings for each input file
	for input_file in get_all_files_in_settings(job_dir, app_name, settings, True):
		# return True if the searched file name is one of the files in the settings
		if os.path.basename(file) == os.path.basename(input_file): return True
	# return False in any other case
	return False

def search_file(app_name, settings, file_tag):
	# search in the settings for each input file
	for input_file in get_all_files_in_settings(job_dir, app_name, settings):
		# return True if the searched file tag is included in one of the files in the settings
		if file_tag in os.path.basename(input_file): return True
	# return False in any other case
	return False
