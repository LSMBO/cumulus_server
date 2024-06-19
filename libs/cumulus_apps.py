#import logging
import os

import cumulus_server.libs.cumulus_config as config
import cumulus_server.libs.cumulus_utils as utils
import cumulus_server.apps.diann181 as diann181
import cumulus_server.apps.diann182 as diann182
import cumulus_server.apps.test_app as test

#logger = logging.getLogger(__name__)
FINAL_FILE = config.get("final.file")

def is_finished(app_name, stdout):
	if app_name == "diann_1.8.1": return diann181.is_finished(stdout)
	elif app_name == "diann_1.8.2": return diann182.is_finished(stdout)
	elif app_name == "test": return test.is_finished(stdout)
	else: return True

def are_all_files_transfered(job_dir, app_name, settings):
	#job_dir = db.get_job_dir(job_id)
	if os.path.isfile(f"{job_dir}/{FINAL_FILE}"):
		if app_name == "diann_1.8.1": return diann181.check_input_files(settings, utils.DATA_DIR)
		elif app_name == "diann_1.8.2": return diann182.check_input_files(settings, utils.DATA_DIR)
		elif app_name == "test": return test.check_input_files(settings, utils.DATA_DIR)
	return False

#def checkParameters(app_name, settings):
#  if app_name == "diann_1.8.1": return diann181.checkParameters(utils.DATA_DIR, settings)
#  elif app_name == "diann_1.8.2": return diann182.checkParameters(utils.DATA_DIR, settings)
#  else: return []

#def get_command_line(job_dir, app_name, settings, host):
#	# get the command line that corresponds to the application
#	cmd = f"cd '{job_dir}'; "
#	if app_name == "diann_1.8.1": cmd += diann181.get_command_line(settings, utils.DATA_DIR, host.cpu)
#	elif app_name == "diann_1.8.2": cmd += diann182.get_command_line(settings, utils.DATA_DIR, host.cpu)
#	elif app_name == "test": cmd += test.get_command_line(settings, utils.DATA_DIR)
#	# default test command
#	else: cmd += "sleep 60 &"
#
#	# make sure the command ends with the log redirection and the ampersand
#	if "1>" not in cmd: cmd += f" 1> {utils.get_stdout_file_name(app_name)}"
#	if "2>" not in cmd: cmd += f" 2> {utils.get_stderr_file_name(app_name)}"
#	if not cmd.endswith(" &"): cmd += " &"
#	return cmd

def generate_script(job_id, job_dir, app_name, settings, host):
	# the working directory is the job directory
	content = f"cd '{job_dir}'\n"
	# the script then must call the proper command line
	cmd = "sleep 60"
	if app_name == "diann_1.8.1": cmd = diann181.get_command_line(settings, utils.DATA_DIR, host.cpu)
	elif app_name == "diann_1.8.2": cmd = diann182.get_command_line(settings, utils.DATA_DIR, host.cpu)
	elif app_name == "test": cmd = test.get_command_line(settings, utils.DATA_DIR)
	# make sure the command ends with the log redirection and the ampersand
	# TODO the stdout & stderr file names should be given by the apps, and this would be the backup names
	if "1>" not in cmd: cmd += f" 1> {utils.get_stdout_file_name(app_name)}"
	if "2>" not in cmd: cmd += f" 2> {utils.get_stderr_file_name(app_name)}"
	content += cmd + "\n"
	# then wait a few seconds to make sure that stdout and stderr are completely written
	# TODO wait longer? how long? is it the real solution?
	content += "sleep 30\n"
	# write the script in the job directory and return the file
	return utils.write_local_file(job_id, "cmd", content)

def is_file_required(app_name, settings, file):
	if app_name == "diann_1.8.1": return diann181.is_file_required(settings, file)
	elif app_name == "diann_1.8.2": return diann182.is_file_required(settings, file)
	elif app_name == "test": return test.is_file_required(settings, file)
	else: return False
