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
import time

import cumulus_server.libs.cumulus_config as config
import cumulus_server.libs.cumulus_utils as utils
import cumulus_server.libs.cumulus_database as db
import cumulus_server.libs.cumulus_apps as apps

logger = logging.getLogger(__name__)

REFRESH_RATE = int(config.get("refresh.rate.in.seconds"))
MAX_AGE = int(config.get("data.max.age.in.days"))

def is_process_running(job_id):
	#pid = db.get_pid(job_id)
	pid = utils.get_pid(job_id)
	host_name = db.get_host(job_id)
	host = utils.get_host(host_name)
	# if the pid is still alive, it's RUNNING
	is_alive = utils.remote_check(host, pid)
	logger.debug(f"Job {job_id} is alive? {is_alive}")
	return is_alive

def check_running_jobs():
	for job_id in db.get_jobs_per_status("RUNNING"):
		# # copy the logs in the log directory
		# utils.store_stdout(job_id)
		# utils.store_stderr(job_id)
		# get stdout
		stdout = utils.get_stdout_content(job_id)
		# check that the process still exist
		if not is_process_running(job_id):
			# if not, the process has ended, record the end date
			db.set_end_date(job_id)
			# ask the proper app module if the job is finished or failed
			if apps.is_finished(db.get_app_name(job_id), stdout): 
				status = "DONE"
				db.set_status(job_id, status)
				logger.info(f"Correct ending of {db.get_job_to_string(job_id)}")
			else:
				status = "FAILED"
				db.set_status(job_id, status)
				logger.warning(f"Failure of {db.get_job_to_string(job_id)}")

def find_best_host(job_id):
	# select the host matching the strategy (best_cpu, best_ram, first_available, <host_name>)
	strategy = db.get_strategy(job_id)
	selected_host = None
	hosts = utils.get_all_hosts()
	
	if strategy == "first_available":
		# if the strategy is to take the first available host, return the first host who is not running anything
		for host in hosts:
			#if host.to_dict()["running"] == 0: selected_host = host
			runnings, _ = db.get_alive_jobs_per_host(host.name)
			if runnings == 0: selected_host = host
	else:
		# otherwise, find the host that fits the strategy
		if strategy == "best_ram":
			for host in hosts:
				if selected_host is None or host.ram > selected_host.ram: selected_host = host 
		elif strategy == "best_cpu":
			for host in hosts:
				if selected_host is None or host.cpu > selected_host.cpu: selected_host = host 
		elif strategy.startswith("host:"):
			# the strategy name may contain the name of an host
			for host in hosts:
				if f"host:{host.name}" == strategy: selected_host = host
		# reset the selected host if it is already in use
		if selected_host is not None:
			runnings, _ = db.get_alive_jobs_per_host(selected_host.name)
			if runnings > 0: selected_host = None
	
	# return the selected host, it can be None
	return selected_host

def start_job(job_id, job_dir, app_name, settings, host):
	# generate the script to run
	cmd_file = apps.generate_script(job_id, job_dir, app_name, settings, host)
	# execute the command
	# pid = utils.remote_script(host, cmd_file)
	logger.info(f"Sending SSH request to start job {job_id} on host '{host}'")
	utils.remote_script(host, cmd_file)
	# update the job
	db.set_host(job_id, host.name)
	db.set_status(job_id, "RUNNING")
	db.set_start_date(job_id)
	# log the command
	logger.info(f"Starting {db.get_job_to_string(job_id)}")
	# return pid

def start_pending_jobs():
	# get all the PENDING jobs, oldest ones first
	for job_id in db.get_jobs_per_status("PENDING"):
		job_dir = db.get_job_dir(job_id)
		app_name = db.get_app_name(job_id)
		settings = db.get_settings(job_id)
		# check that all the files are present
		if apps.are_all_files_transfered(job_dir, app_name, settings):
			logger.info(f"Job {job_id} is ready to start")
			# check that there is an available host matching the strategy
			host = find_best_host(job_id)
			# if all is ok, the job can start and its status can turn to RUNNING
			if host is not None: start_job(job_id, job_dir, app_name, settings, host)
			else: logger.warning(f"No host available for job {job_id}...")

def run():
	# wait a little before starting the daemon
	time.sleep(10)
	# possible statuses: PENDING, RUNNING, DONE, FAILED, CANCELLED, ARCHIVED
	while True:
		# check the running jobs to see if they are finished
		check_running_jobs()
		# get all the PENDING jobs, oldest ones first
		start_pending_jobs()
		# sleep for 30 seconds before checking the jobs again
		time.sleep(REFRESH_RATE)

def clean():
	# TODO this has not been tested yet!
	# wait a minute before starting the daemon
	time.sleep(60)
	# clean the old files once a day
	while True:
		# list the job directories and remove those who are DONE|FAILED and too old, set the status to ARCHIVED
		for job in os.listdir(utils.JOB_DIR):
			job_id = int(job.split("_")[1])
			job_dir = utils.JOB_DIR + "/" + job
			#logger.warning(f"Checking job {job_id} stored in '{job}'")
			if utils.get_file_age_in_days(job_dir) > MAX_AGE:
				# if job does not exist in the database, delete its folder
				if not db.check_job_existency(job_id):
					logger.warning(f"Job {job_id} had content but was not found in the database, deleting all content")
					utils.delete_job_folder_no_db(job_dir)
					# TODO also delete log files
				else:
					status = db.get_status(job_id)
					if status == "DONE" or status == "FAILED" or status == "CANCELLED":
						db.set_status(job_id, "ARCHIVED_" + status)
						utils.delete_job_folder(job_dir)
						logger.warning(f"Job {job_id} has been archived and its content has been deleted")
		# list the raw files that are too old, if they are not used in any RUNNING|PENDING job delete them
		for file in os.listdir(utils.DATA_DIR):
			file = utils.DATA_DIR + "/" + file
			if utils.get_file_age_in_days(file) > MAX_AGE:
				# verify if this file is used or will be used
				is_used = False
				for job_id in db.get_jobs_per_status("RUNNING") + db.get_jobs_per_status("PENDING"):
					if apps.is_file_required(db.get_app_name(job_id), db.get_settings(job_id), file):
						is_used = True
						break
				if not is_used: 
					utils.delete_raw_file(file)
					logger.warning(f"File {os.path.basename(file)} has been deleted due to old age")
		# wait 24 hours between each cleaning
		time.sleep(86400)
