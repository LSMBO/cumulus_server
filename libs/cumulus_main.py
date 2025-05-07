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
	# create a pending job, it will be started when the files are all available, return the job id
	job_id, job_dir = db.create_job(request.form)
	utils.create_job_directory(job_dir, request.form)
	logger.info(f"Create job {job_id}")
	return jsonify(job_id, job_dir)

@app.route("/joblist/<int:job_id>/<int:number>/")
def job_list(job_id, number):
	return jsonify(db.get_last_jobs(job_id, number))

@app.route("/search", methods=["POST"])
def search_jobs():
	logger.info("Search jobs")
	return jsonify(db.search_jobs(request.form))

@app.route("/cancel/<string:owner>/<int:job_id>")
def cancel(owner, job_id):
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
	# return an array of dicts, one per host
	# each dict contains its name, the number of cpu, the amount of ram and the numbers of jobs running and pending
	return jsonify(list(map(lambda host: host.to_dict(), utils.get_all_hosts(True))))

@app.route("/apps")
def listapps():
	# return an array of xml strings, let the client extract the information
	return jsonify(apps.get_app_list())

@app.route("/storage")
def storage():
	# return the file names and sizes in /storage/data (as a string)
	return jsonify(utils.get_raw_file_list())

@app.route("/diskusage")
def diskusage():
	return jsonify(utils.get_disk_usage())

@app.route("/fail", methods=["POST"])
def fail_job():
	logger.info("Fail job")
	utils.set_job_failed(request.form["job_id"], request.form["error_message"])

@app.route("/config")
def check(): return jsonify(config.export())

def start():
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
	# start the daemons once all functions are defined
	threading.Thread(target=daemon.run, args=(), daemon=True).start()
	threading.Thread(target=daemon.clean, args=(), daemon=True).start()
	# start waitress WSGI server
	serve(app, host = config.get("local.host"), port = config.get("local.port"))
