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

def get_stdout(job_id):
	content = ""
	job_dir = db.get_job_dir(job_id)
	if os.path.isdir(job_dir):
		app_name = db.get_app_name(job_id)
		file = f"{job_dir}/{utils.get_stdout_file_name(app_name)}"
		if os.path.isfile(file):
			f = open(file, "r")
			content = f.read()
			f.close()
		else: logger.debug(f"Log file '${file}' is missing")
	else: logger.debug(f"Job directory '${job_dir}' is missing")
	return content

def get_stderr(job_id): 
	content = ""
	job_dir = db.get_job_dir(job_id)
	if os.path.isdir(job_dir):
		app_name = db.get_app_name(job_id)
		file = f"{job_dir}/{utils.get_stderr_file_name(app_name)}"
		if os.path.isfile(file):
			f = open(f"{job_dir}/{utils.get_stderr_file_name(app_name)}", "r")
			content = f.read()
			f.close()
		else: logger.debug(f"Log file '${file}' is missing")
	else: logger.debug(f"Job directory '${job_dir}' is missing")
	return content

def is_process_running(job_id):
	pid = db.get_pid(job_id)
	host_name = db.get_host(job_id)
	host = utils.get_host(host_name)
	#_, stdout, _ = utils.remote_exec(host, f"ps -p {pid} -o comm=")
	# if the pid is still alive, it's RUNNING
	#logger.debug(f"Job {job_id} output from 'ps -p {pid}' at '{host.name}': '{stdout}'")
	#return False if stdout.at_eof() else True
	#return stdout != ""
	is_alive = utils.remote_check(host, pid)
	logger.debug(f"Job {job_id} is alive? {is_alive}")
	return is_alive

#def is_job_finished(job_id):
#	#app_name = db.get_app_name(job_id)
#	# get latest logs
#	stdout = get_stdout(job_id)
#	stderr = get_stderr(job_id)
#	# ask the proper app module if the job is actually done
#	is_done = apps.is_finished(db.get_app_name(job_id), stdout)
#	# store the logs at the end
#	db.set_stdout(job_id, stdout)
#	db.set_stderr(job_id, stderr)
#	return is_done
#
#def check_running_jobs():
#	for job_id in db.get_jobs_per_status("RUNNING"):
#		# check that the process still exist
#		if not is_process_running(job_id):
#			# if not, it means that the process either ended or failed
#			status = "DONE" if is_job_finished(job_id) else "FAILED"
#			db.set_status(job_id, status)
#			db.set_end_date(job_id)
#			if status == "DONE": logger.info(f"Correct ending of {db.get_job_to_string(job_id)}")
#			else: logger.warning(f"Failure of {db.get_job_to_string(job_id)}")
#			# store stdout and stderr
#			#db.set_stdout(job_id, get_stdout(job_id))
#			#db.set_stderr(job_id, get_stderr(job_id))

def check_running_jobs():
	for job_id in db.get_jobs_per_status("RUNNING"):
		# update the stdout & stderr content
		stdout = get_stdout(job_id)
		stderr = get_stderr(job_id)
		db.set_stdout(job_id, stdout)
		db.set_stderr(job_id, stderr)
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
		#if selected_host.to_dict()["running"] > 0: selected_host = None
		if selected_host is not None:
			runnings, _ = db.get_alive_jobs_per_host(selected_host.name)
			if runnings > 0: selected_host = None
	
	# return the selected host, it can be None
	return selected_host

#def start_job(job_id, host):
def start_job(job_id, job_dir, app_name, settings, host):
	## set the command line
	##cmd = apps.get_command_line(db.get_app_name(job_id), db.get_settings(job_id), host)
	#cmd = apps.get_command_line(job_dir, app_name, settings, host)
	## write the command line into a .cumulus.cmd file in the job dir
	#cmd_file = utils.write_local_file(job_id, "cmd", cmd)
	# generate the script to run
	cmd_file = apps.generate_script(job_id, job_dir, app_name, settings, host)
	# execute the command
	#pid, _, _ = utils.remote_exec(host, cmd)
	#pid = utils.remote_exec_script(host, cmd_file)
	pid = utils.remote_script(host, cmd_file)
	# also write the pid to a .cumulus.pid file
	utils.write_local_file(job_id, "pid", str(pid))
	# update the job
	db.set_pid(job_id, str(pid))
	db.set_host(job_id, host.name)
	db.set_status(job_id, "RUNNING")
	db.set_start_date(job_id)
	# log the command
	logger.info(f"Starting {db.get_job_to_string(job_id)}")
	return pid

def start_pending_jobs():
	# get all the PENDING jobs, oldest ones first
	for job_id in db.get_jobs_per_status("PENDING"):
		job_dir = db.get_job_dir(job_id)
		app_name = db.get_app_name(job_id)
		settings = db.get_settings(job_id)
		# check that all the files are present
		# FIXME pending jobs are not running
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
	# wait a minute before starting the daemon
	time.sleep(60)
	# clean the old files once a day
	while True:
		# list the job directories and remove those who are DONE|FAILED and too old, set the status to ARCHIVED
		for job in os.listdir(utils.JOB_DIR):
			job_id = int(job.split("_")[1])
			job = utils.JOB_DIR + "/" + job
			logger.warning(f"Checking job {job_id} stored in '{job}'")
			if utils.get_file_age_in_days(job) > MAX_AGE:
				status = db.get_status(job_id)
				if status == "DONE" or status == "FAILED" or status == "CANCELLED":
					db.set_status(job_id, "ARCHIVED")
					utils.delete_job_folder(job)
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
				if not is_used: utils.delete_raw_file(file)
		# wait 24 hours between each cleaning
		time.sleep(86400)
