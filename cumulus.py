from flask import Flask
from flask import jsonify
from flask import request
from flask import send_file
import logging
from logging.handlers import RotatingFileHandler
import os
import threading

# local modules
import cumulus_server.libs.cumulus_utils as utils
import cumulus_server.libs.cumulus_database as db
import cumulus_server.libs.cumulus_daemon as daemon

app = Flask(__name__)
logger = logging.getLogger(__name__)
logging.basicConfig(
	handlers = [RotatingFileHandler(filename = "cumulus.log", maxBytes = 100000, backupCount = 10)],
	#level = logging.DEBUG,
	level = logging.INFO,
	format = "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
	datefmt = '%Y/%m/%d %H:%M:%S')

# this has to be a POST message
@app.route("/start", methods=["POST"])
def start():
	# create a pending job, it will be started when the files are all available, return the job id
	job_id, job_dir = db.create_job(request.form, utils.JOB_DIR)
	utils.create_job_directory(job_dir, request.form)
	logger.info(f"Create job ${job_id}")
	return str(job_id)

# get details for a job
@app.route("/details/<int:job_id>")
def details(job_id):
	# return the job's owner, its app, the settings, status, host, description, stdout, stderr, and all three dates
	return jsonify(db.get_job_details(job_id))

@app.route("/jobs/<string:host>/<string:owner>/<string:app_name>/<string:tag>/<int:number>/")
def jobs(host, owner, app_name, tag, number):
	if host == "*": host = "%"
	if owner == "*": owner = "%"
	if app_name == "*": app_name = "%"
	if tag == "*": tag = "%"
	return jsonify(db.get_job_list(host, owner, app_name, tag, number))

@app.route("/status/<int:job_id>")
def status(job_id):
	return jsonify(db.get_job_status(job_id))

@app.route("/cancel/<string:owner>/<int:job_id>")
def cancel(owner, job_id):
	# TODO there should be some real security here to avoid cancelling stuff too easily
	if db.is_owner(job_id, owner):
		logger.info(f"Cancel job ${job_id}")
		# read the status file, only cancel if the status is RUNNING
		status = db.get_status(job_id)
		if status == "PENDING" or status == "RUNNING": utils.cancel_job(job_id)
		# a previous cancel may not have been able to remove the folder, try again now
		elif status == "FAILED" or status == "CANCELLED": utils.delete_job_folder(job_id)
		return f"Job {job_id} has been deleted"
	else: return f"You cannot delete this job"

@app.route("/getfilelist/<string:owner>/<int:job_id>")
def get_file_list(owner, job_id):
	# return the list of files for the job
	if db.is_owner(job_id, owner): return utils.get_file_list(job_id)
	# if the user is not the owner, return an empty list
	else: return []

@app.route("/getresults/<string:owner>/<int:job_id>/<file_name>")
def get_results(owner, job_id, file_name):
	file = f"{db.get_job_dir(job_id)}/{file_name}"
	# check that the user can download the results
	if db.is_owner(job_id, owner) and db.get_status(job_id) == "DONE":
		# check that the file exists
		if os.path.isfile(file):
			# return the file
			try:
				send_file(file)
			except Exception as e:
				db.add_to_stderr(job_id, f"Error on [get_results], {e.strerror}: {file}")
				return str(e)
	# in every other case, return an empty string?
	return ""

@app.route("/info")
def info():
	# return an array of dicts, one per host
	# each dict contains its name, the number of cpu, the amount of ram and the numbers of jobs running and pending
	return jsonify(list(map(lambda host: host.to_dict(), utils.get_all_hosts(True))))

@app.route("/storage")
def storage():
	# return the file names and sizes in /storage/data (as a string)
	return jsonify(utils.get_raw_file_list())

@app.route("/version")
def version(): return utils.get_version()

# start the daemons once all functions are defined
threading.Thread(target=daemon.run, args=(), daemon=True).start()
threading.Thread(target=daemon.clean, args=(), daemon=True).start()
