import os
import sqlite3

DB = "jobs.db"

def connect():
    # connect to the database, create it if it does not exist yet
    # cnx = sqlite3.connect(DB, autocommit = True)
    cnx = sqlite3.connect(DB)
    cursor = cnx.cursor()
    # create the main table if it does not exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
        owner TEXT NOT NULL,
        appname TEXT NOT NULL,
        settings TEXT NOT NULL,
        status TEXT NOT NULL,
        host TEXT,
        pid INTEGER)
    """)
    return cnx, cursor

def setValue(job_id, field, value):
    # connect to the database
    cnx, cursor = connect()
    # TODO test that it does not fail if the job_id does not exist
    cursor.execute(f"UPDATE jobs SET {field} = ? WHERE id = ?", (value, job_id))
    # disconnect
    cnx.close()

def getValue(job_id, field):
    # connect to the database
    cnx, cursor = connect()
    # TODO test that it does not fail if the job_id does not exist
    cursor.execute(f"SELECT {field} FROM jobs WHERE id = ?", job_id)
    value = cursor.fetchone() if cursor.arraysize > 0 else ""
    # disconnect and return the value
    cnx.close()
    return value

def getAllStatuses():
    # connect to the database
    cnx, cursor = connect()
    # TODO test that it does not fail if the job_id does not exist
    results = cursor.execute(f"SELECT id, status FROM jobs SORT BY id DESC")
    statuses = []
    for id, status in results:
        statuses.append([id, status])
    # disconnect and return the value
    cnx.close()
    return statuses

# fields with getters and setters
def setStatus(job_id, status): setValue(job_id, "status", status)
def getStatus(job_id): return getValue(job_id, "status")
def setHost(job_id, host): setValue(job_id, "host", host)
def getHost(job_id): return getValue(job_id, "host")
def setPid(job_id, pid): setValue(job_id, "pid", pid)
def getPid(job_id): return getValue(job_id, "pid")
# fields with getters only
#def getCommandLine(job_id): return getValue(job_id, "command")
def getSettings(job_id): return eval(getValue(job_id, "settings"))
def getAppName(job_id): return getValue(job_id, "appname")
def isOwner(job_id, owner): return getValue(job_id, "owner") == owner

def createJob(owner, appname, settings, host = None)
    # connect to the database
    cnx, cursor = connect()
    # status should be PENDING when created, RUNNING when it's started, DONE if it's finished successfully, FAILED if it's finished in error
    # pid should be null if the job has not started yet, or if it's finished
    # host should be the ip address of the vm where it's going to be executed, it could be null if the first available vm is to be picked
    cursor.execute(f"INSERT INTO jobs VALUES (?, ?, ?, ?)", owner, appname, str(settings), "PENDING")
    # return the id of the job
    job_id = cursor.lastrowid
    # disconnect
    cnx.close()
    # add the host if it's already known
    if host != None: setHost(job_id, host)
    # return the job_id
    return job_id

# we want to get the next job in the queue, for a given vm
def getNextJob(host):
    # connect to the database
    cnx, cursor = connect()
    # search the next job that is not dedicated to another host
    cursor.execute("SELECT id, host from jobs WHERE status = 'PENDING' AND (host IS NULL OR host = ?) LIMIT 1", host)
    # there might be no next job
    job_id, job_host = cursor.fetchone() if cursor.arraysize > 0 else ""
    # update the host if it was not given
    if job_host == "": cursor.execute("UPDATE jobs SET host = ? WHERE id = ?", host, job_id)
    # disconnect and return the value
    cnx.close()
    return job_id

def isHostAvailable(host):
    # connect to the database
    cnx, cursor = connect()
    # make sure that the host is given
    if host != None:
      # count the number of jobs that are running on this host
      cursor.execute("SELECT count(*) FROM jobs WHERE status = 'RUNNING' AND host = ?", host)
      return True if cursor.fetchone() = 0 else False
    else:
      return False

def getJobList(host = "", jobsAliveOnly = False)
    # id, owner, appname, status, host
    # connect to the database
    cnx, cursor = connect()
    # prepare the conditions eventually
    conditions = ""
    conditions += f" AND host = '{host}'" if host != ""
    conditions += " AND status = 'PENDING' OR status = 'RUNNING'" if jobsAliveOnly
    # search the next job that is not dedicated to another host (the first condition is just to simplify the addition of other conditions)
    results = cursor.execute("SELECT id, owner, appname, status, host from jobs WHERE id > 0" + conditions)
    # put the results in a dict
    jobs = {}
    for id, owner, appname, status, host in results:
        jobs[id] = {"owner": owner, "appname": appname, "status": status, "host": host}
    # disconnect and return the dict
    cnx.close()
    return jobs
