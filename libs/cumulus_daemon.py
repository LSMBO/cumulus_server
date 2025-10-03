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
import threading
import time

import libs.cumulus_config as config
import libs.cumulus_utils as utils
import libs.cumulus_database as db
import libs.cumulus_apps as apps

logger = logging.getLogger(__name__)

REFRESH_RATE = int(config.get("refresh.rate.in.seconds"))
# MAX_AGE = int(config.get("data.max.age.in.days"))
MZML_CONVERSION_RUNNING = False

def is_process_running(job_id):
	"""
	Check if a process associated with a given job ID is currently running.

	This function first retrieves the process ID (PID) and host name for the specified job.
	It checks if the process is alive using a local file listing all pids for a given host. 
	If the process is not found there, it attempts a remote check on the specified host.

	Args:
		job_id (int): The unique identifier for the job whose process status is to be checked.

	Returns:
		bool: True if the process is running, False otherwise.
	"""
	# prepare information to check the process
	# host_name = db.get_host(job_id)
	is_alive = False
	# get all the jobs that are associated to this job_id (could be several if the job is part of a workflow)
	for id in db.get_associated_jobs(job_id):
		logger.debug(f"Checking if the process for job {id} is still running")
		# two files are used to check if the job is still running:
		alive_file = db.get_job_dir(id) + "/" + config.JOB_ALIVE_FILE # the alive file is created when the job starts
		logger.debug(f"Searching for alive file {alive_file}: exists={os.path.exists(alive_file)}")
		stop_file = db.get_job_dir(id) + "/" + config.JOB_STOP_FILE # the stop file is created when the job ends
		logger.debug(f"Searching for stop file {stop_file}: exists={os.path.exists(stop_file)}")
		# if the alive file exists, it must have been updated recently (less than 3 minutes ago) to consider that the job is still running
		# if os.path.exists(alive_file): is_alive = time.time() - os.path.getmtime(alive_file) < 180
		if os.path.exists(alive_file): 
			# is_alive = time.time() - os.path.getmtime(alive_file) < 180
			previous_time = db.get_last_modified(id)
			current_time = os.path.getmtime(alive_file)
			logger.debug(f"Alive file {alive_file} was last modified at {previous_time}, current modification time is {current_time}")
			is_alive = current_time > previous_time
			if is_alive: db.set_last_modified(id, int(current_time))
		# if the alive file does not exist, check if the stop file exists, in this case, the job has stopped
		elif os.path.exists(stop_file): is_alive = False
		# there should always be an alive file or a stop file, but if none of them exist, we consider that the job is not running
		# else: is_alive = False
		# if there is no alive file and no stop file, it's probably because the job is not running yet
		# TODO if the job has crashed before running, this could lead to a job remaining in RUNNING status forever
		else: is_alive = True
	# return the status directly
	return is_alive

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
	for job_id in db.get_jobs_per_status("PREPARING"):
		# if the host could not be created, the job has failed
		job_dir = db.get_job_dir(job_id)
		# if the host is not yet created, do nothing and wait for the next check
		host_file = f"{job_dir}/{config.HOST_FILE}"
		if not os.path.exists(host_file): continue # TODO what if the file was not yet created?
		# get the host that was generated
		host = utils.get_host_from_file(f"{job_dir}/{config.HOST_FILE}")
		# abort if the host could not be created
		if host is None:
			db.set_status(job_id, "FAILED")
			db.set_end_date(job_id)
			logger.error(f"Cannot create the host for job {job_id}, aborting")
			# if the file is not created yet, it may be because the server was stopped during this phase
			# in that case, we should recall start_job
		elif host.error is not None:
			db.set_status(job_id, "FAILED")
			db.set_end_date(job_id)
			logger.error(f"Cannot create the host for job {job_id}, error was: {host.error}, aborting")
		else:
			# the host has been created, the job can start
			db.set_status(job_id, "RUNNING")
			db.set_start_date(job_id)
	for job_id in db.get_jobs_per_status("RUNNING"):
		# check that the process still exist
		if not is_process_running(job_id):
			# destroy the worker VM in the background
			threading.Thread(target=utils.destroy_worker, args=(job_id,)).start()
			# record the end date
			db.set_end_date(job_id)
			# ask the proper app module if the job is finished or failed
			if apps.is_finished(job_id, db.get_app_name(job_id)): 
				db.set_status(job_id, "DONE")
				logger.info(f"Correct ending of {db.get_job_to_string(job_id)}")
			else:
				db.set_status(job_id, "FAILED")
				db.set_end_date(job_id)
				logger.warning(f"Failure of {db.get_job_to_string(job_id)}")

def start_job(job_id, job_dir, app_name, settings, flavor, job_details):
	"""
	Starts a job on a remote host by generating and executing a script, then updates the job status in the database.
	Note: This function is intended to be run in a separate thread to avoid blocking the main daemon loop. That's why
	it takes all the parameters instead of fetching them from the database (otherwise it may get a locked database error).

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
	# create symbolic links of the raw files into the input folder
	apps.link_shared_files(job_dir, app_name, settings)
	# create the worker based on the template worker
	utils.create_worker(job_id, job_dir, flavor)
	# get the host that was generated
	host = utils.get_host_from_file(f"{job_dir}/{config.HOST_FILE}")
	# abort if the host could not be created
	if host is not None and host.error is None:
		# create the script to run the job
		cmd_file, content = apps.generate_script_content(job_id, job_dir, app_name, settings, host.cpu)
		utils.write_file(cmd_file, content)
		# wait until all the files are there (mzML conversion may still be running at this point)
		while not apps.are_all_files_transfered(job_dir, app_name, settings):
			# wait 10 seconds
			time.sleep(10)
		# start the remote script to run the job
		utils.add_to_stdalt(job_id, f"Remotely execute the job {job_id} on the virtual machine")
		# remote_cmd = f"{config.JOB_START_FILE} {job_id} '{job_dir}'"
		remote_cmd = f"{config.JOB_START_FILE} '{job_dir}'"
		utils.remote_script(host, remote_cmd)
		# log the command owner, app_name, status, strategy
		# logger.info(f"Starting {db.get_job_to_string(job_id)}")
		logger.info(f"Starting {job_details}")

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
			# the strategy of the job must tell us which flavor to use
			flavor = utils.check_flavor(job_id)
			if flavor is None:
				logger.warning(f"No host available for job {job_id} with flavor '{flavor}' at this moment")
			else:
				# directly set the host and the status to RUNNING in the database to avoid starting another job on the same host
				db.set_status(job_id, "PREPARING")
				# create the new VM with this flavor
				# run this in a thread, and call start_job once the host is created
				# the status will remain PENDING until the host is created and the job started
				threading.Thread(target=start_job, args=(job_id, job_dir, app_name, settings, flavor, db.get_job_to_string(job_id))).start()
		else:
			logger.debug(f"Job {job_id} is NOT ready to start YET")

def restart_paused_jobs():
	# Special case for PAUSED jobs, only happen when restarting the server
	# The PAUSED status should only exist between a shutdown and a restart
	for job_id in db.get_jobs_per_status("PAUSED"):
		# restarting this job immediately
		logger.info(f"Resume job {job_id}")
		db.set_status(job_id, "PREPARING")
		# in this case, we consider that everything is already prepared
		job_dir = db.get_job_dir(job_id)
		app_name = db.get_app_name(job_id)
		settings = db.get_settings(job_id)
		flavor = utils.check_flavor(job_id)
		threading.Thread(target=start_job, args=(job_id, job_dir, app_name, settings, flavor, db.get_job_to_string(job_id))).start()

def run():
	"""
	Runs the main daemon loop for managing jobs.

	This function initializes the configuration, waits briefly before starting,
	and then enters an infinite loop to:
		- Reload the application list if updates are detected.
		- Check the status of running jobs and update their states.
		- Start any pending jobs, prioritizing the oldest ones.
		- Sleep for a defined refresh rate before repeating the process.

	Possible job statuses include: PENDING, PREPARING, RUNNING, DONE, FAILED, CANCELLED, ARCHIVED_DONE, ARCHIVED_FAILED, ARCHIVED_CANCELLED.
	"""
	# load the config file
	config.init()
	# wait a little before starting the daemon
	time.sleep(10)
	# possible statuses: PENDING, PREPARING, RUNNING, DONE, FAILED, CANCELLED, ARCHIVED_DONE, ARCHIVED_FAILED, ARCHIVED_CANCELLED
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
			utils.delete_job_folder(job_dir, False, True)
			logger.warning(f"Job {job_id} has been archived and its content has been deleted")
		# list the folders in the job directory that are not linked to any job
		for job_dir in utils.get_zombie_jobs():
			logger.warning(f"Job folder {job_dir} is not linked to any real job and will be deleted")
			utils.delete_folder(job_dir)
		# list the shared files that are old and not used
		for file in utils.get_unused_shared_files_older_than(max_age_in_seconds):
			utils.delete_raw_file(file)
			logger.warning(f"File {os.path.basename(file)} has been deleted due to old age")
		# wait 24 hours between each cleaning
		time.sleep(86400)

def convert_raw_to_mzml():
	"""
	Converts raw data files to mzML format for pending jobs.
	This function checks for pending jobs and converts their associated raw data files to mzML format if they haven't been converted yet.
	It ensures that only one conversion process runs at a time using a global flag.
	This function is not exactly a daemon, as it is intended to be called periodically from the main daemon loop.
	But is has to be called in a separate thread to avoid blocking the main daemon loop.
	"""
	global MZML_CONVERSION_RUNNING
	# if a conversion is already running, do nothing
	if MZML_CONVERSION_RUNNING: return
	# set a flag to indicate that the conversion is running
	MZML_CONVERSION_RUNNING = True
	# wait a little before starting the conversion
	time.sleep(10)
	# list all the pending jobs, oldest ones first
	for job_id in db.get_jobs_per_status("PENDING"):
		# get the list of raw files that need to be converted to mzML
		job_dir = db.get_job_dir(job_id)
		app_name = db.get_app_name(job_id)
		settings = db.get_settings(job_id)
		files_to_convert = apps.get_files(job_dir, app_name, settings, False, True)
		# get the first file that needs to be converted, and is not being converted yet
		for file in files_to_convert:
			mzml_file = utils.get_mzml_file_path(file)
			temp_file = utils.get_mzml_file_path(file, True)
			# if there is one, and it does not exist yet, and is not being converted yet, we will convert it
			if not os.path.exists(mzml_file) and not os.path.exists(temp_file):
				utils.convert_to_mzml(job_id, file)
		# update the symbolic links in the input folder
		apps.link_shared_files(job_dir, app_name, settings)
	# reset the flag to indicate that the conversion is not running anymore
	MZML_CONVERSION_RUNNING = False
	
