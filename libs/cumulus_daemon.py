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

def getStdout(job_id):
  content = ""
  if os.path.isfile(JOB_DIR + "/" + job_id):
    settings = db.getSettings(job_id)
    f = open(f"{JOB_DIR}/{job_id}/{utils.getStdoutFileName(settings['appname'])}", "r")
    content = f.read()
    f.close()
  return content

def getStderr(job_id): 
  content = ""
  if os.path.isfile(JOB_DIR + "/" + job_id):
    settings = db.getSettings(job_id)
    f = open(f"{JOB_DIR}/{job_id}/{utils.getStderrFileName(settings['appname'])}", "r")
    content = f.read()
    f.close()
  return content

def isProcessRunning(job_id):
  pid = db.getPid(job_id)
  host = db.getHost(job_id)
  _, stdout, _ = utils.remoteExec(host, f"ps -p {pid} -o comm=")
  # if the pid is still alive, it's RUNNING
  return False if stdout.at_eof() else True

def isJobFinished(job_id):
  #appName = db.getAppName(job_id)
  # get latest logs
  stdout = getStdout(job_id)
  stderr = getStderr(job_id)
  # ask the proper app module if the job is actually done
  isDone = apps.isFinished(stdout)
  # store the logs at the end
  db.setStdOut(stdout)
  db.setStdErr(stderr)
  return isDone

def checkRunningJobs():
  for job_id in db.getJobsPerStatus("RUNNING"):
    # check that the process still exist
    if not isProcessRunning(job_id):
      # if not, it means that the process either ended or failed
      status = "DONE" if isJobFinished(job_id) else "FAILED"
      db.setStatus(job_id, status)
      db.setEndDate(job_id)
      if status == "DONE": logger.info(f"Correct ending of {db.getJobToString(job_id)}")
      else: logger.warning(f"Failure of {db.getJobToString(job_id)}")

def findBestHost(job_id):
  # select the host matching the strategy (best_cpu, best_ram, first_available, <host_name>)
  strategy = db.getStrategy(job_id)
  selected_host = None
  hosts = utils.getAllHosts()
  
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
    #elif strategy != "first_available":
    elif strategy.startswith("host:"):
      # the strategy name may contain the name of an host
      for host in hosts:
        if f"host:{host.name}" == strategy: selected_host = host
    # reset the selected host if it is already in use
    if selected_host.toDict()["running"] > 0: selected_host = None
  
  # return the selected host, it can be None
  return selected_host

def startJob(job_id, host):
  # set the command line
  cmd = apps.getCommandLine(db.getAppName(job_id), db.getSettings(job_id), host)
  # execute the command
  pid, _, _ = remoteExec(host, cmd)
  # update the job
  db.setPid(job_id, pid)
  db.setHost(job_id, host)
  db.setStatus(job_id, "RUNNING")
  db.setStartDate(job_id)
  # log the command
  logger.info(f"Starting {db.getJobToString(job_id)}")
  return pid

def startPendingJobs():
  # get all the PENDING jobs, oldest ones first
  for job_id in db.getJobsPerStatus("PENDING"):
    # check that all the files are present
    #if utils.areAllFilesTransfered(job_id):
    if apps.areAllFilesTransfered(job_id, db.getAppName(job_id), db.getSettings(job_id)):
      # check that there is an available host matching the strategy
      host = findBestHost(job_id)
      # if all is ok, the job can start and its status can turn to RUNNING
      if host is not None: startJob(job_id, selected_host)

def run():
  # wait a minute before starting the daemon
  time.sleep(60)
  # possible statuses: PENDING, RUNNING, DONE, FAILED, ARCHIVED
  while True:
    ## archive the DONE|FAILED jobs for which the job folder have been erased over time
    #utils.archiveJobs()
    # check the running jobs to see if they are finished
    checkRunningJobs()
    # get all the PENDING jobs, oldest ones first
    startPendingJobs()
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
      if utils.getFileAgeInDays(job) > MAX_AGE:
        status = db.getStatus(job_id)
        if status == "DONE" or status == "FAILED":
          db.setStatus(job_id, "ARCHIVED")
          utils.deleteJobFolder(job)
    # list the raw files that are too old, if they are not used in any RUNNING|PENDING job delete them
    for file in os.listdir(utils.DATA_DIR):
      file = utils.DATA_DIR + "/" + file
      if utils.getFileAgeInDays(file) > MAX_AGE:
        # verify if this file is used or will be used
        is_used = False
        for job_id in db.getJobsPerStatus("RUNNING") + db.getJobsPerStatus("PENDING"):
          if apps.is_file_required(db.getAppName(job_id), db.getSettings(job_id), file):
            is_used = True
            break
        if not is_used: utils.deleteRawFile(file)
    # wait 24 hours between each cleaning
    time.sleep(86400)
