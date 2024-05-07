import paramiko
import os
import shutils
# local modules
import cumulus-db as db
import diann181
import diann182

STORAGE = "/home/ubuntu/storage"
DATA_DIR = STORAGE + "/data"
JOB_DIR = STORAGE + "/jobs"
VM_FILE = "/home/ubuntu/controller/VM.tsv"

class VM:
    def __init__(self, name, host, port, user, rsa_key, cpu, ram):
        self.name = name
        self.host = host
        self.port = port
        self.user = user
        self.rsa_key = rsa_key
        self.cpu = cpu
        self.ram = ram
    def __str__(self):
        return f"{self.name}\t{self.host}\t{self.port}\t{self.user}\t{self.cpu}\t{self.ram}"
    def toDict(self):
        current_jobs = db.getJobList(host = self.host, jobsAliveOnly = True)
        runnings = dict(filter(lambda p: p[1]["status"] == "RUNNING", current_jobs.items()))
        pendings = dict(filter(lambda p: p[1]["status"] == "PENDING", current_jobs.items()))
        return {"name": self.name, "cpu": self.cpu, "ram": self.ram, "jobs_running": runnings, "jobs_pending": pendings}

def getAllVirtualMachines():
    vms = []
    # get the list of VMs from the file
    f = open(VM_FILE, "r")
    for vm in f.read().strip("\n").split("\n"):
        vms.append(VM(vm.split("\t")))
    f.close()
    # remove first item of the list, it's the header of the file
    vms.pop(0)
    # return the list
    return vms

def getCredentials(ip):
    # open the file to search for the ip and return the match
    for vm in getAllVirtualMachines():
        if vm.host == ip: return vm.user, vm.rsa, vm.port
    # return empty values if there is no vm with that ip address
    return "", "", 0

def remoteExec(ip, command):
    # get the credentials
    user, key, port = getCredentials(ip)
    # TODO check that the VM exists and decide what to return if it does not
    # connect to the VM
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, port=port, username=user, pkey = key)
    # execute the command remotely
    #stdin, stdout, stderr = channel.exec_command(command)
    _, stdout, stderr = ssh.exec_command("echo $$ && exec " + command)
    pid = int(stdout.readline())
    # convert the outputs to text
    stdout = stdout.read().decode('ascii').strip("\n")
    stderr = stderr.read().decode('ascii').strip("\n")
    # close the connection and return outputs
    ssh.close()
    return pid, stdout, stderr

def isProcessRunning(job_id):
    pid = db.getPid(job_id)
    host = db.getHost(job_id)
    _, stdout, _ = remoteExec(host, f"ps -p {pid} -o comm=")
    # if the pid is still alive, it's RUNNING
    return False if stdout.at_eof() else return True

def selectVirtualMachine(strategy):
    # load the list of VMs
    vms = getAllVirtualMachines()
    # user can choose between different strategies
    # - best_cpu, wait until it's free
    # - best_ram, wait until it's free
    # - default would be to use the first available VM, or wait until one is free
    # TODO user could ask for a specific VM?
    selected_vm = None
    if strategy == "best_cpu":
        for vm in vms:
            if vm.cpu > selected_vm.cpu: selected_vm = vm
    elif strategy == "best_ram":
        for vm in vms:
            if vm.ram > selected_vm.ram: selected_vm = vm
    else:
        for vm in vms:
            if db.isHostAvailable(vm.host): selected_vm = vm
    # selected_vm may still be None if all VMs are used at the moment
    return selected_vm

def getVirtualMachine(host):
  for vm in getAllVirtualMachines():
    if vm.host == host: return vm
  return None

def getJobDir(job_id): return JOB_DIR + "/" + job_id

def getStdoutFileName(appName): return f".{appName}.stdout"

def getStderrFileName(appName): return f".{appName}.stderr"

def getStdout(job_id): 
    content = ""
    if os.path.isfile(JOB_DIR + "/" + job_id):
        settings = db.getSettings(job_id)
        f = open(f"{JOB_DIR}/{job_id}/{getStdoutFileName(settings['appname'])}", "r")
        content = f.read()
        f.close()
    return content

def getStderr(job_id): 
    content = ""
    if os.path.isfile(JOB_DIR + "/" + job_id):
        settings = db.getSettings(job_id)
        f = open(f"{JOB_DIR}/{job_id}/{getStderrFileName(settings['appname'])}", "r")
        content = f.read()
        f.close()
    return content

def getFileTuple(file):
    return (file, os.path.getsize(file))

def getFileList(job_id):
    filelist = []
    if os.path.isfile(JOB_DIR + "/" + job_id):
        # list all files including sub-directories
        root_path = JOB_DIR + "/" + job_id + "/"
        for root, dirs, files in os.walk(root_path):
            # make sure that the file pathes are relative to the root of the job folder
            rel_path = root.replace(root_path, "")
            for f in files:
                #if rel_path == "": filelist.append(f)
                #else: filelist.append(rel_path + "/" + f)
                # return an array of tuples (name|size)
                if rel_path == "": filelist.append(getFileTuple(f))
                else: filelist.append(getFileTuple(rel_path + "/" + f))
    # the user will select the files they want to retrieve
    return filelist

def checkParameters(job_id):
    settings = db.getSettings(job_id)
    if appName == "diann_1.8.1": return diann181.checkParameters(DATA_DIR, settings)
    elif appName == "diann_1.8.2": return diann182.checkParameters(DATA_DIR, settings)
    else: return []

def getCommandLine(job_id):
    # get informations about the job
    vm = getVirtualMachine(db.getHost(job_id))
    settings = db.getSettings(job_id)
    appName = settings['appname']

    # get the command line that corresponds to the application
    cmd = ""
    if appName == "diann_1.8.1": cmd = diann181.getCommandLine(settings, DATA_DIR, vm.cpu)
    elif appName == "diann_1.8.2": cmd = diann182.getCommandLine(settings, DATA_DIR, vm.cpu)
    # default test command
    else: cmd = "sleep 60 &"

    # make sure the command ends with the log redirection and the ampersand
    if "1>" not in cmd: cmd += f" 1> {getStdoutFileName(appName)}"
    if "2>" not in cmd: cmd += f" 2> {getStderrFileName(appName)}"
    if not cmd.endswith(" &"): cmd += " &"
    return cmd

def writeToStderr(job_id, text):
    f = open(getStderrFileName(db.getAppName(job_id)), "a")
    f.write(f"\nControllerError: {text}\n")
    f.close()

def startJob(job_id):
    # make some final checks
    errors = []
    host = db.getHost(job_id)
    if host == "": errors.append(f"No host for the job {job_id}")
    errors.extend(checkParameters(job_id))
    # create the job directory, even if there are errors (they will be written in the stderr file there)
    # it means that a job in error may have its folder remaining until someone removes it manually...
    if not os.path.isfile(JOB_DIR + "/" + job_id): os.mkdir(JOB_DIR + "/" + job_id)
    # run the job if there is no error
    if len(errors) == 0:
        # get informations
        cmd = getCommandLine(job_id)
        # if no host was stored, use the first one available (do it here or before?)
        # execute the command
        pid, _, _ = remoteExec(host, cmd)
        # update the job
        db.setPid(job_id, pid)
        db.setStatus(job_id, "RUNNING")
    else:
        db.setStatus(job_id, "FAILED")
        for err in errors: writeToStderr(job_id, err)

def createJob(settings):
    # get a suitable VM based on the requested strategy
    vm = selectVirtualMachine(settings['strategy'])
    host = None if vm == None else vm.host
    # create the job in the database and get its id
    job_id = db.createJob(settings['username'], settings['appname'], settings, host)
    # start the job if it's possible
    if db.getNextJob(host) == job_id: startJob(job_id)
    return job_id

def isJobFinished(job_id):
    appName = db.getAppName(job_id)
    stdout = getStdout(job_id)
    stderr = getStderr(job_id)
    if appname == "diann_1.8.1": return diann181.isFinished(stdout)
    elif appname == "diann_1.8.2": return diann182.isFinished(stdout)
    else: return False
    
def deleteJobFolder(job_id):
    try:
        shutils.rmtree(JOB_DIR + "/" + job_id)
        return true
    except OSError as o:
        print(f"Error, {o.strerror}: {JOB_DIR}/{job_id}")
        db.setStatus(job_id, "FAILED")
        return false

def cancelJob(job_id):
    # get the pid and the host
    pid = db.getPid(job_id)
    host = db.getHost(job_id)
    # use ssh to kill the pid
    remoteExec(host, f"kill -9 {pid}")
    # delete the job directory
    return deleteJobFolder(job_id)
