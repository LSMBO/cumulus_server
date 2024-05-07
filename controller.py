from flask import Flask
from flask import request
from flask import send_file
import os
# local modules
import cumulus-utils as cu
import cumulus-db as db

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

#@app.route("/login", methods=["POST"])
#def login():
    # TODO use a session and a database to store users?
    # for now, just request the login of the owner, it's not secure but it's easy
#    return "token?"

# this has to be a POST message
@app.route("/start", methods=["POST"])
def start():
    # parameters are in request.form['param'] = value
    # create the job, get a VM, launch the job if possible, return the job_id
    return cu.createJob(request.form)

@app.route("/status/")
@app.route("/status/<int:job_id>")
def status(job_id = None):
    # if no job_id is given, return a dict of job_id -> status, without the log files
    if job_id == None:
        # return a list of [job_id:status], most recent first
        return db.getAllStatuses()
    else:
      # get the status from the database
      status = db.getStatus(job_id)
      # if the job has not ended yet, check if the status has to be updated
      if status != "DONE" and status != "FAILED":
          if not os.path.isfile(cu.getJobDir(job_id)): status = "PENDING"
          elif cu.isProcessRunning(job_id): status = "RUNNING"
          elif cu.isJobFinished(job_id): status = "DONE"
          else: status = "FAILED"
      db.setStatus(job_id, status)
      # if the job has finished or failed, start a new one
      if status != "RUNNING":
          next_job_id = db.getNextJob(getHost(job_id))
          if next_job_id != "": cu.startJob(next_job_id)
      # return the status and the log content
      return status, cu.getStdout(job_id), cu.getStderr(job_id)

@app.route("/cancel/<string:owner>/<int:job_id>")
def cancel(owner, job_id):
    # TODO there should be some real security here to avoid cancelling stuff too easily
    if db.isOwner(job_id, owner):
        # read the status file, only cancel if the status is RUNNING
        status = db.getStatus(job_id)
        if status == "RUNNING": return cu.cancelJob(job_id)
        # a previous cancel may not have been able to remove the folder, try again now
        elif status == "FAILED": return cu.deleteJobFolder(job_id)
    return False

@app.route("/getfilelist/<string:owner>/<int:job_id>")
def get_file_list(owner, job_id):
    # return the list of files for the job
    if db.isOwner(job_id, owner): return cu.getFileList(job_id)
    # if the user is not the owner, return an empty list
    else: return []

@app.route("/getresults/<string:owner>/<int:job_id>/<file_name>")
def get_results(owner, job_id, file_name):
    job_dir = cu.getJobDir(job_id)
    # check that the user can download the results
    if db.isOwner(job_id, owner) and db.getStatus(job_id) == "DONE":
        # check that the file exists
        if os.path.isfile(job_dir + "/" + file_name):
            # return the file
            try:
                send_file(job_dir + "/" + file_name)
            except Exception as e:
                print(f"Error on [get_results], {e.strerror}: {job_dir}/${file_name}")
                return str(e)
    # in every other case, return an empty string?
    return ""

@app.route("/info")
def info():
    # return an array of dicts, one per VM
    # each dict contains its name, the number of cpu, the amount of ram and the numbers of jobs running and pending
    vms = []
    for vm in cu.getAllVirtualMachines():
        vms.append(vm.toDict())
    return vms

