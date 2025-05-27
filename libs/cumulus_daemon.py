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
import time

import libs.cumulus_config as config
import libs.cumulus_utils as utils
import libs.cumulus_database as db
import libs.cumulus_apps as apps

logger = logging.getLogger(__name__)

REFRESH_RATE = int(config.get("refresh.rate.in.seconds"))
# MAX_AGE = int(config.get("data.max.age.in.days"))

def is_process_running(job_id):
	"""
	Check if a process associated with a given job ID is currently running.

	This function first retrieves the process ID (PID) and host name for the specified job.
	It checks if the process is alive using a local file listing all pids for a given host. 
	If the process is not found there, it attempts a remote check on the specified host.

	Args:
		job_id (str or int): The unique identifier for the job whose process status is to be checked.

	Returns:
		bool: True if the process is running, False otherwise.
	"""
	pid = utils.get_pid(job_id)
	host_name = db.get_host(job_id)
	# if the pid is still alive, it's RUNNING
	is_alive = utils.is_alive(host_name, str(pid))
	# logger.debug(f"Job {job_id} is alive? {is_alive}")
	if is_alive: 
		return True
	else:
		# check directly on the host if the pid is still alive (it may not be in the pid file yet)
		logger.debug(f"Job {job_id} was not found in the pid file, sending a request to {host_name}")
		host = utils.get_host(host_name)
		return utils.remote_check(host, pid)

def check_running_jobs():
	"""
	Checks all jobs with status "RUNNING" to determine if their associated processes are still active.

	For each running job:
	- Verifies if the process is still running.
	- If the process is not running:
		- Records the job's end date.
		- Determines if the job finished successfully or failed using the appropriate app module.
		- Updates the job's status to "DONE" or "FAILED" accordingly.
		- Logs the outcome (success or failure) with job details.

	This function relies on external modules for database access, process checking, and application-specific job status evaluation.
	"""
	for job_id in db.get_jobs_per_status("RUNNING"):
		# # get stdout
		# stdout = apps.get_stdout_content(job_id)
		# # get job_dir
		# job_dir = db.get_job_dir(job_id)
		# check that the process still exist
		if not is_process_running(job_id):
			# the pid may not be in the pid file yet, as it is reloaded every 60 seconds
			# if not, the process has ended, record the end date
			db.set_end_date(job_id)
			# ask the proper app module if the job is finished or failed
			# if apps.is_finished(db.get_app_name(job_id), stdout): 
			if apps.is_finished(job_id, db.get_app_name(job_id)): 
				status = "DONE"
				db.set_status(job_id, status)
				logger.info(f"Correct ending of {db.get_job_to_string(job_id)}")
			else:
				status = "FAILED"
				db.set_status(job_id, status)
				db.set_end_date(job_id)
				logger.warning(f"Failure of {db.get_job_to_string(job_id)}")

def find_host(job_id):
	"""
	Finds and returns an available host for a given job based on the specified scheduling strategy.

	Args:
		job_id (str or int): The identifier of the job for which a host is to be found.

	Returns:
		Host or None: The first available host object that matches the strategy and is not currently running any jobs.
		Returns None if no suitable host is available at the moment.

	Behavior:
		- Retrieves the scheduling strategy for the job from the database.
		- If no strategy is set, defaults to "first_available" and logs a warning.
		- Gets a list of hosts matching the strategy.
		- Returns the first host that is not running any jobs.
		- Logs a debug message and returns None if no host is available.
	"""
	# select the host matching the strategy (best_cpu, best_ram, first_available, <host_name>)
	strategy = db.get_strategy(job_id)
	if strategy == "": 
		logger.warning(f"No strategy is given for job {job_id}, use the first available host instead")
		db.set_strategy(job_id, "first_available")
	# get the list of hosts matching the strategy
	hosts = utils.get_hosts_for_strategy(strategy)
	# return the first host that is not running anything
	for host in hosts:
		_, running = db.get_alive_jobs_per_host(host.name)
		if running == 0: return host
	# if no host is available, return None
	logger.debug(f"No host available for job {job_id} with strategy '{strategy}' at this moment, maybe later...")
	return None

def start_job(job_id, job_dir, app_name, settings, host):
	"""
	Starts a job on a remote host by generating and executing a script, then updates the job status in the database.

	Args:
		job_id (str): Unique identifier for the job.
		job_dir (str): Directory where the job files are located.
		app_name (str): Name of the application to run.
		settings (dict): Dictionary of settings for the job/application.
		host (Host): Host object representing the remote machine where the job will run.

	Side Effects:
		- Generates a script file for the job and writes it to disk.
		- Executes the script remotely via SSH on the specified host.
		- Updates the job's host, status, and start date in the database.
		- Logs information about the job execution process.
	"""
	# generate the script to run
	# cmd_file = apps.generate_script(job_id, job_dir, app_name, settings, host.cpu)
	cmd_file, content = apps.generate_script_content(job_id, job_dir, app_name, settings, host.cpu)
	utils.write_file(cmd_file, content)
	# execute the command
	logger.info(f"Sending SSH request to start job {job_id} on host '{host.name}'")
	utils.remote_script(host, cmd_file)
	# update the job
	db.set_host(job_id, host.name)
	db.set_status(job_id, "RUNNING")
	db.set_start_date(job_id)
	# log the command
	logger.info(f"Starting {db.get_job_to_string(job_id)}")

def start_pending_jobs():
	"""
	Starts all pending jobs that are ready to run.

	This function iterates through all jobs with a "PENDING" status, checks if all required files have been transferred,
	and if so, attempts to find an available host according to the job's strategy. If a suitable host is found, the job
	is started and its status is updated to "RUNNING". If not all files are present or no host is available, the job
	remains pending and appropriate log messages are generated.

	Logging:
		- Logs debug information for each job's status.
		- Logs info when a job is ready to start.
		- Logs a warning if no host is available for a ready job.
		- Logs debug information if a job is not ready to start yet.

	Dependencies:
		- Relies on external modules/functions: db, apps, find_host, start_job, and logger.
	"""
	# get all the PENDING jobs, oldest ones first
	for job_id in db.get_jobs_per_status("PENDING"):
		logger.debug(f"Job {job_id} is PENDING")
		job_dir = db.get_job_dir(job_id)
		app_name = db.get_app_name(job_id)
		settings = db.get_settings(job_id)
		# check that all the files are present
		if apps.are_all_files_transfered(job_dir, app_name, settings):
			logger.info(f"Job {job_id} is ready to start")
			# check that there is an available host matching the strategy
			host = find_host(job_id)
			# if all is ok, the job can start and its status can turn to RUNNING
			if host is not None: start_job(job_id, job_dir, app_name, settings, host)
			else: logger.warning(f"No host available for job {job_id}...")
		else:
			logger.debug(f"Job {job_id} is NOT ready to start YET")

def run():
	"""
	Runs the main daemon loop for managing jobs.

	This function initializes the configuration, waits briefly before starting,
	and then enters an infinite loop to:
		- Reload the application list if updates are detected.
		- Check the status of running jobs and update their states.
		- Start any pending jobs, prioritizing the oldest ones.
		- Sleep for a defined refresh rate before repeating the process.

	Possible job statuses include: PENDING, RUNNING, DONE, FAILED, CANCELLED, ARCHIVED_DONE, ARCHIVED_FAILED, ARCHIVED_CANCELLED.
	"""
	# load the config file
	config.init()
	# wait a little before starting the daemon
	time.sleep(10)
	# possible statuses: PENDING, RUNNING, DONE, FAILED, CANCELLED, ARCHIVED_DONE, ARCHIVED_FAILED, ARCHIVED_CANCELLED
	while True:
		# reload the app list if needed (allows to update the app list without restarting the daemon)
		if apps.is_there_app_update(): apps.get_app_list()
		# check the running jobs to see if they are finished
		check_running_jobs()
		# get all the PENDING jobs, oldest ones first
		start_pending_jobs()
		# sleep for 30 seconds before checking the jobs again
		time.sleep(REFRESH_RATE)

def clean():
	"""
	Periodically cleans up old and unused files and directories related to jobs.

	This function performs the following maintenance tasks in an infinite loop, running once every 24 hours after an initial 60-second delay:
	- Archives and deletes job folders for jobs that have ended and are older than the configured maximum age.
	- Deletes job directories that are not linked to any existing job ("zombie" job folders).
	- Deletes log files that are not associated with any job.
	- Deletes shared files that are old and unused.

	All deletions and archival actions are logged with warnings.

	Note:
		The maximum age for jobs and shared files is determined by the "data.max.age.in.days" configuration value.
	"""
	# wait a minute before starting the daemon
	time.sleep(60)
	# clean the old files once a day
	while True:
		# list the jobs older than the max age in seconds
		max_age_in_seconds = int(config.get("data.max.age.in.days")) * 86400
		for job_id, status, job_dir in db.get_ended_jobs_older_than(max_age_in_seconds):
			db.set_status(job_id, "ARCHIVED_" + status)
			utils.delete_job_folder(job_dir)
			logger.warning(f"Job {job_id} has been archived and its content has been deleted")
		# list the folders in the job directory that are not linked to any job
		for job_dir in utils.get_zombie_jobs():
			logger.warning(f"Job folder {job_dir} is not linked to any real job and will be deleted")
			utils.delete_job_folder_no_db(job_dir)
		# delete log files that are not linked to any job
		zombie_log_files = utils.get_zombie_log_files()
		if len(zombie_log_files) > 0: logger.warning(f"{len(zombie_log_files)} log files are not linked to any real job and will be deleted")
		for log_file in zombie_log_files:
			os.remove(log_file)
		# list the shared files that are old and not used
		for file in utils.get_unused_shared_files_older_than(max_age_in_seconds):
			utils.delete_raw_file(file)
			logger.warning(f"File {os.path.basename(file)} has been deleted due to old age")
		# wait 24 hours between each cleaning
		time.sleep(86400)
