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

import cumulus_server.libs.cumulus_config as config
import cumulus_server.libs.cumulus_utils as utils
import cumulus_server.apps.diann181 as diann181
import cumulus_server.apps.diann191 as diann191
import cumulus_server.apps.test_app as test

logger = logging.getLogger(__name__)
FINAL_FILE = config.get("final.file")

def is_finished(app_name, stdout):
	if app_name == "diann_1.8.1": return diann181.is_finished(stdout)
	elif app_name == "diann_1.9.1": return diann191.is_finished(stdout)
	elif app_name == "test": return test.is_finished(stdout)
	else: return True

def are_all_files_transfered(job_dir, app_name, settings):
	if os.path.isfile(f"{job_dir}/{FINAL_FILE}"):
		if app_name == "diann_1.8.1": return diann181.check_input_files(settings, job_dir, utils.DATA_DIR)
		elif app_name == "diann_1.9.1": return diann191.check_input_files(settings, job_dir, utils.DATA_DIR)
		elif app_name == "test": return test.check_input_files(settings, job_dir, utils.DATA_DIR)
	else: logger.debug(f"{job_dir} is still expecting files, {FINAL_FILE} is not there yet...")
	return False

def generate_script(job_id, job_dir, app_name, settings, host):
	# the working directory is the job directory
	content = f"cd '{job_dir}'\n"
	# create a directory where the output files should be generated
	output_dir = "./output"
	content += f"mkdir '{output_dir}'\n"
	# the script then must call the proper command line
	cmd = "sleep 60"
	if app_name == "diann_1.8.1": cmd = diann181.get_command_line(settings, utils.DATA_DIR, host.cpu, output_dir)
	elif app_name == "diann_1.9.1": cmd = diann191.get_command_line(settings, utils.DATA_DIR, host.cpu, output_dir)
	elif app_name == "test": cmd = test.get_command_line(settings, utils.DATA_DIR, output_dir)
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
	if app_name == "diann_1.8.1": return diann181.is_file_required(settings, file)
	elif app_name == "diann_1.9.1": return diann191.is_file_required(settings, file)
	elif app_name == "test": return test.is_file_required(settings, file)
	else: return False

def search_file(app_name, settings, file):
	if app_name == "diann_1.8.1": return diann181.search_file(settings, file)
	elif app_name == "diann_1.9.1": return diann191.search_file(settings, file)
	elif app_name == "test": return test.search_file(settings, file)
	else: return False

