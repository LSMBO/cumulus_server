import logging
import os
import paramiko
import shutils
import time

import libs.cumulus_config as config
import libs.cumulus_database as db

logger = logging.getLogger(__name__)

#STORAGE = "/home/ubuntu/storage"
#DATA_DIR = STORAGE + "/data"
#JOB_DIR = STORAGE + "/jobs"
DATA_DIR = config.get("storage.data.path")
JOB_DIR = config.get("storage.jobs.path")
#HOST_FILE = "/home/ubuntu/controller/hosts.tsv"

class Host:
  # TODO maybe add a max number of jobs per host?
  def __init__(self, name, address, port, user, rsa_key, cpu, ram):
    self.name = name
    self.address = address
    self.port = port
    self.user = user
    self.rsa_key = rsa_key
    self.cpu = cpu
    self.ram = ram
  def __str__(self):
    return f"{self.name}\t{self.address}\t{self.port}\t{self.user}\t{self.cpu}\t{self.ram}"
  def toDict(self):
    #current_jobs = db.getJobList(address = self.address, jobsAliveOnly = True)
    #runnings = dict(filter(lambda p: p[1]["status"] == "RUNNING", current_jobs.items()))
    #pendings = dict(filter(lambda p: p[1]["status"] == "PENDING", current_jobs.items()))
    runnings, pendings = db.getAliveJobsPerHost(self.name)
    return {"name": self.name, "cpu": self.cpu, "ram": self.ram, "jobs_running": runnings, "jobs_pending": pendings}

def getAllHosts():
  hosts = []
  # get the list of hosts from the file
  #f = open(HOST_FILE, "r")
  f = open(config.get("hosts.file.path"), "r")
  for host in f.read().strip("\n").split("\n"):
    hosts.append(Host(host.split("\t")))
  f.close()
  # remove first item of the list, it's the header of the file
  hosts.pop(0)
  # return the list
  return hosts

def getCredentials(ip):
  # open the file to search for the ip and return the match
  for host in getAllHosts():
    if host.address == ip: return host.user, host.rsa, host.port
  # return empty values if there is no host with that ip address
  return "", "", 0

def remoteExec(ip, command):
  # get the credentials
  user, key, port = getCredentials(ip)
  # connect to the host
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(ip, port = port, username = user, pkey = key)
  # execute the command remotely
  _, stdout, stderr = ssh.exec_command("echo $$ && exec " + command)
  pid = int(stdout.readline())
  # convert the outputs to text
  stdout = stdout.read().decode('ascii').strip("\n")
  stderr = stderr.read().decode('ascii').strip("\n")
  # close the connection and return outputs
  ssh.close()
  return pid, stdout, stderr

def createJobDirectory(job_id):
  if not os.path.isfile(JOB_DIR + "/" + job_id): os.mkdir(JOB_DIR + "/" + job_id)

def getsize(file):
  if os.path.isfile(file):
    return os.path.getsize(file)
  else:
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(file):
      for f in filenames:
        fp = os.path.join(dirpath, f)
        # skip if it is symbolic link
        if not os.path.islink(fp): total_size += os.path.getsize(fp)
    return total_size

def getRawFileList():
  filelist = []
  for file in os.listdir(DATA_DIR):
    filelist.append((file, getsize(file)))

def getFileList(job_id):
  filelist = []
  if os.path.isfile(JOB_DIR + "/" + job_id):
    # list all files including sub-directories
    root_path = JOB_DIR + "/" + job_id + "/"
    for root, dirs, files in os.walk(root_path):
      # make sure that the file pathes are relative to the root of the job folder
      rel_path = root.replace(root_path, "")
      for f in files:
        # return an array of tuples (name|size)
        file = f if rel_path == "" else rel_path + "/" + f
        filelist.append((file, getsize(file)))
    # the user will select the files they want to retrieve
    return filelist

def deleteRawFile(file):
  try:
    if os.path.isfile(file): os.remove(file)
    else: shutils.rmtree(file)
  except OSError as o:
    logger.error(f"Can't delete raw file {file}: {o.strerror}")

def deleteJobFolder(job_id):
  try:
    shutils.rmtree(JOB_DIR + "/" + job_id)
    return true
  except OSError as o:
    db.setStatus(job_id, "FAILED")
    logger.error(f"Can't delete job folder for {db.getJobToString(job_id)}: {o.strerror}")
    addToStderr(job_id, f"Can't delete job folder for {db.getJobToString(job_id)}: {o.strerror}")
    return false

def cancelJob(job_id):
  # get the pid and the host
  pid = db.getPid(job_id)
  host = db.getHost(job_id)
  # use ssh to kill the pid
  remoteExec(host, f"kill -9 {pid}")
  # delete the job directory
  return deleteJobFolder(job_id)

#def archiveJobs():
#  # get all the DONE|FAILED jobs
#  for job_id in db.getJobsPerStatus("DONE"):
#    # if the job folder has been removed, set the status to ARCHIVED
#    if not os.path.isfile(JOB_DIR + "/" + job_id): db.setStatus(job_id, "ARCHIVED")
#  # do the same with FAILED jobs
#  for job_id in db.getJobsPerStatus("FAILED"):
#    if not os.path.isfile(JOB_DIR + "/" + job_id): db.setStatus(job_id, "ARCHIVED")

def getJobDir(job_id): return JOB_DIR + "/" + job_id
def getStdoutFileName(appName): return f".{appName}.stdout"
def getStderrFileName(appName): return f".{appName}.stderr"

#def areAllFilesTransfered(job_id):
#  return os.path.isfile(JOB_DIR + "/.RSYNC_OK")

def getFileAgeInDays(file):
  # mtime is the date in seconds since epoch since the last modification
  # time() is the current time
  # divide by the number of seconds in a day to have the number of days
  return (time.time() - os.path.getmtime(file)) / 86400

def getVersion(): return config.get("version")