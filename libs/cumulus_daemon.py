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
  if os.path.isfile(JOB_DIR + "/" + job_id):
    settings = db.get_settings(job_id)
    f = open(f"{JOB_DIR}/{job_id}/{utils.get_stdout_file_name(settings['app_name'])}", "r")
    content = f.read()
    f.close()
  return content

def get_stderr(job_id): 
  content = ""
  if os.path.isfile(JOB_DIR + "/" + job_id):
    settings = db.get_settings(job_id)
    f = open(f"{JOB_DIR}/{job_id}/{utils.get_stderr_file_name(settings['app_name'])}", "r")
    content = f.read()
    f.close()
  return content

def is_process_running(job_id):
  pid = db.get_pid(job_id)
  host = db.get_host(job_id)
  _, stdout, _ = utils.remote_exec(host, f"ps -p {pid} -o comm=")
  # if the pid is still alive, it's RUNNING
  return False if stdout.at_eof() else True

def is_job_finished(job_id):
  #app_name = db.get_app_name(job_id)
  # get latest logs
  stdout = get_stdout(job_id)
  stderr = get_stderr(job_id)
  # ask the proper app module if the job is actually done
  is_done = apps.is_finished(stdout)
  # store the logs at the end
  db.set_stdout(stdout)
  db.set_stderr(stderr)
  return is_done

def check_running_jobs():
  for job_id in db.get_jobs_per_status("RUNNING"):
    # check that the process still exist
    if not is_process_running(job_id):
      # if not, it means that the process either ended or failed
      status = "DONE" if is_job_finished(job_id) else "FAILED"
      db.set_status(job_id, status)
      db.set_end_date(job_id)
      if status == "DONE": logger.info(f"Correct ending of {db.get_job_to_string(job_id)}")
      else: logger.warning(f"Failure of {db.get_job_to_string(job_id)}")

def find_best_host(job_id):
  # select the host matching the strategy (best_cpu, best_ram, first_available, <host_name>)
  strategy = db.get_strategy(job_id)
  selected_host = None
  hosts = utils.get_all_hosts()
  
  if strategy == "first_available":
    # if the strategy is to take the first available host, return the first host who is not running anything
    for host in hosts:
      if host.toDict()["running"] == 0: selected_host = host
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
    if selected_host.toDict()["running"] > 0: selected_host = None
  
  # return the selected host, it can be None
  return selected_host

def start_job(job_id, host):
  # set the command line
  cmd = apps.get_command_line(db.get_app_name(job_id), db.get_settings(job_id), host)
  # execute the command
  pid, _, _ = remote_exec(host, cmd)
  # update the job
  db.set_pid(job_id, pid)
  db.set_host(job_id, host)
  db.set_status(job_id, "RUNNING")
  db.set_start_date(job_id)
  # log the command
  logger.info(f"Starting {db.get_job_to_string(job_id)}")
  return pid

def start_pending_jobs():
  # get all the PENDING jobs, oldest ones first
  for job_id in db.get_jobs_per_status("PENDING"):
    # check that all the files are present
    if apps.are_all_files_transfered(job_id, db.get_app_name(job_id), db.get_settings(job_id)):
      # check that there is an available host matching the strategy
      host = find_best_host(job_id)
      # if all is ok, the job can start and its status can turn to RUNNING
      if host is not None: start_job(job_id, selected_host)

def run():
  # wait a minute before starting the daemon
  time.sleep(60)
  # possible statuses: PENDING, RUNNING, DONE, FAILED, ARCHIVED
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
    for job_id in os.listdir(utils.JOB_DIR):
      job = utils.JOB_DIR + "/" + job_id
      if utils.get_file_age_in_days(job) > MAX_AGE:
        status = db.get_status(job_id)
        if status == "DONE" or status == "FAILED":
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
