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

from flask import Flask
from flask import jsonify
from flask import request
from flask import send_file
import logging
from logging.handlers import RotatingFileHandler
import os
import threading
from urllib.parse import unquote
from waitress import serve

# local modules
import libs.cumulus_apps as apps
import libs.cumulus_config as config
import libs.cumulus_utils as utils
import libs.cumulus_database as db
import libs.cumulus_daemon as daemon

IS_DEBUG = False
if os.getenv("CUMULUS_DEBUG"): IS_DEBUG = True

app = Flask(__name__)
logger = logging.getLogger(__name__)

# this has to be a POST message
@app.route("/start", methods=["POST"])
def start():
	"""
	Creates a pending job and its associated directory, then returns the job ID and directory.

	This function performs the following steps:
	1. Creates a pending job using data from the request form and retrieves the job ID and directory.
	2. Creates the job directory with the provided form data.
	3. Logs the creation of the job.
	4. Returns a JSON response containing the job ID and directory.

	Returns:
		Response: A Flask JSON response with the job ID and job directory.
	"""
	# create a pending job, it will be started when the files are all available, return the job id
	job_id, job_dir = db.create_job(request.form)
	utils.create_job_directory(job_dir, request.form)
	logger.info(f"Create job {job_id}")
	return jsonify(job_id, job_dir)

@app.route("/joblist/<int:job_id>/<int:number>/")
def job_list(job_id, number):
	"""
	Retrieve a list of the most recent jobs for a given job ID.

	Args:
		job_id (int): The identifier of the job to retrieve.
		number (int): The number of recent jobs to return.

	Returns:
		flask.Response: A JSON response containing the list of recent jobs.
						The job corresponding to job_id will be detailed, all other jobs will be summarized.

	"""
	return jsonify(db.get_last_jobs(job_id, number))

@app.route("/search", methods=["POST"])
def search_jobs():
	"""
	Handles the search for jobs based on the provided form data.

	Logs the search action and returns the search results as a JSON response.

	Returns:
		flask.Response: A JSON response containing the search results. 
						The job corresponding to job_id will be detailed, all other jobs will be summarized.
	"""
	logger.info("Search jobs")
	return jsonify(db.search_jobs(request.form))

@app.route("/cancel/<string:owner>/<int:job_id>")
def cancel(owner, job_id):
	"""
	Attempts to cancel a job if the requesting owner is authorized.

	Parameters:
		owner (str): The identifier of the user attempting to cancel the job.
		job_id (int): The unique identifier of the job to be cancelled.

	Returns:
		str: A message indicating the result of the cancellation attempt. Possible messages include:
			- Confirmation that the job has been cancelled.
			- Notification that the job cannot be cancelled because it is already stopped.
			- Notification that the user is not authorized to cancel the job.

	Notes:
		- Only the owner of the job can cancel it.
		- Only jobs with status "PENDING" or "RUNNING" can be cancelled.
		- There is a TODO for implementing stronger security checks.
	"""
	# TODO there should be some real security here to avoid cancelling stuff too easily
	if db.is_owner(job_id, owner):
		logger.info(f"Cancel job ${job_id}")
		# read the status file, only cancel if the status is RUNNING
		status = db.get_status(job_id)
		if status == "PENDING" or status == "RUNNING": 
			utils.cancel_job(job_id)
			return f"Job {job_id} has been cancelled"
		else: return f"Job {job_id} cannot be cancelled, it is already stopped"
	else: return f"You cannot cancel this job"

@app.route("/delete/<string:owner>/<int:job_id>")
def delete(owner, job_id):
	"""
	Deletes a job if the requesting owner is authorized and the job is not running or pending.

	Args:
		owner (str): The owner requesting the deletion.
		job_id (int): The unique identifier of the job to be deleted.

	Returns:
		str: A message indicating the result of the deletion attempt.

	Notes:
		- Only the owner of the job can delete it.
		- Jobs can only be deleted if their status is not "PENDING" or "RUNNING".
		- Additional security checks should be implemented to prevent unauthorized deletions.
	"""
	# TODO there should be some real security here to avoid cancelling stuff too easily
	if db.is_owner(job_id, owner):
		logger.info(f"Delete job ${job_id}")
		# read the status file, only delete if the status is DONE, FAILED or ARCHIVED
		status = db.get_status(job_id)
		if status != "PENDING" and status != "RUNNING":
			utils.delete_job_folder(job_id, True)
			return f"Job {job_id} has been deleted"
		else: return f"You cannot delete a running job"
	else: return f"You cannot delete this job"

@app.route("/getresults/<string:owner>/<int:job_id>/<path:file_name>")
def get_results(owner, job_id, file_name):
	"""
	Retrieve and send a result file for a given job if the requesting user is the owner.

	Args:
		owner (str): The username or identifier of the user requesting the file.
		job_id (int): The unique identifier of the job whose results are being requested.
		file_name (str): The name of the file to retrieve.

	Returns:
		Response: The file as a Flask response object if the user is authorized and the file exists.
		str: An error message if an exception occurs during file sending.
		str: An empty string if the user is not authorized or the file does not exist.

	Notes:
		- Only the owner of the job can download its results.

	Side Effects:
		Logs errors to stderr using utils.add_to_stderr if file sending fails.
	"""
	file = f"{db.get_job_dir(job_id)}/{unquote(file_name)}"
	# check that the user can download the results
	if db.is_owner(job_id, owner):
		# check that the file exists
		if os.path.isfile(file):
			# return the file
			try:
				return send_file(file)
			except Exception as e:
				utils.add_to_stderr(job_id, f"Error on [get_results], {e.strerror}: {file}")
				return str(e)
	# in every other case, return an empty string
	return ""

@app.route("/info")
def info():
	"""
	Returns information about all hosts as a JSON response.

	Each host is represented as a dictionary containing:
		- name: The name of the host.
		- cpu: The number of CPUs available on the host.
		- ram: The amount of RAM available on the host.
		- jobs_running: The number of jobs currently running on the host.
		- jobs_pending: The number of jobs pending on the host.

	Returns:
		flask.Response: A JSON response containing a list of host information dictionaries.
	"""
	# return an array of dicts, one per host
	# each dict contains its name, the number of cpu, the amount of ram and the numbers of jobs running and pending
	return jsonify(list(map(lambda host: host.to_dict(), utils.get_all_hosts(True))))

@app.route("/apps")
def listapps():
	"""
	Returns a JSON response containing a list of available applications.

	The response is an array of XML strings, allowing the client to extract the necessary information.

	Returns:
		flask.Response: A JSON response with the list of application XML strings.
	"""
	# return an array of xml strings, let the client extract the information
	return jsonify(apps.get_app_list())

@app.route("/storage")
def storage():
	"""
	Returns a JSON response containing the list of file names and their sizes in the /storage/data directory.

	Returns:
		flask.Response: A JSON response with the raw file list as provided by utils.get_raw_file_list().
	"""
	# return the file names and sizes in /storage/data (as a string)
	return jsonify(utils.get_raw_file_list())

@app.route("/diskusage")
def diskusage():
	"""
	Returns the current disk usage statistics as a JSON response.

	This function retrieves disk usage information using the `get_disk_usage` function from the `utils` module,
	and returns the result as a JSON response using Flask's `jsonify`.

	Returns:
		flask.Response: A Flask response object containing the disk usage statistics in JSON format.
	"""
	return jsonify(utils.get_disk_usage())

@app.route("/fail", methods=["POST"])
def fail_job():
	"""
	Handles a job failure request by extracting the job ID and error message from the request form,
	logging the failure, and marking the job as failed using the utility function.

	This route is used in the RSync Agent, when some input files are not available. 
	It allows the agent to report a failure without wasting time transferring files that cannot be processed.

	Returns:
		str: An empty string as a response.
	"""
	job_id = request.form["job_id"]
	error_message = request.form["error_message"]
	logger.info(f"Fail job {job_id}: {error_message}")
	utils.set_job_failed(job_id, error_message)
	return ""

@app.route("/config")
def check(): 
	"""
	Returns the current configuration as a JSON response.

	Uses the `jsonify` function to serialize the output of `config.export()`.
	This route is used to check if the server can be reached, to retrieve the current configuration and to check its version number.

	Returns:
		Response: A Flask Response object containing the exported configuration in JSON format.
	"""
	return jsonify(config.export())

def start():
	"""
	Initializes logging, starts background daemon threads, and launches the Waitress WSGI server.

	- Prepares a logs directory if it does not exist.
	- Configures logging with different handlers and levels depending on debug mode.
	- Starts the main daemon thread and, if not in debug mode, a cleaning daemon thread.
	- Runs the Waitress server with the configured host and port.

	Raises:
		OSError: If the logs directory cannot be created.
		Exception: Propagates exceptions from daemon threads or server startup.
	"""
	# prepare the logs
	logs_dir = "logs"
	if not os.path.isdir(logs_dir): os.mkdir(logs_dir)
	log_format = "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s"
	log_date = "%Y/%m/%d %H:%M:%S"
	if IS_DEBUG: logging.basicConfig(level = logging.DEBUG, format = log_format, datefmt = log_date)
	else:
		logging.basicConfig(
			handlers = [RotatingFileHandler(filename = f"{logs_dir}/cumulus.log", maxBytes = 10000000, backupCount = 10)],
			level = logging.INFO,
			format = log_format,
			datefmt = log_date
		)
	# initialize the database
	db.initialize_database()
	# start the daemons once all functions are defined
	threading.Thread(target=daemon.run, args=(), daemon=True).start()
	if not IS_DEBUG: threading.Thread(target=daemon.clean, args=(), daemon=True).start()
	# start waitress WSGI server
	serve(app, host = config.get("local.host"), port = config.get("local.port"))
