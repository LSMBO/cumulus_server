import logging
import os
import sqlite3
import time

import libs.cumulus_config as config

logger = logging.getLogger(__name__)
#DB = "cumulus.db"

def connect():
    # connect to the database, create it if it does not exist yet
    # cnx = sqlite3.connect(DB, autocommit = True)
    cnx = sqlite3.connect(config.get("database.file.path"))
    cursor = cnx.cursor()
    # create the main table if it does not exist
    cursor.execute("""
      CREATE TABLE IF NOT EXISTS jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
        owner TEXT NOT NULL,
        appname TEXT NOT NULL,
        strategy TEXT NOT NULL,
        description TEXT NOT NULL,
        settings TEXT NOT NULL,
        status TEXT NOT NULL,
        host TEXT,
        pid INTEGER,
        creation_date INTEGER DEFAULT unixepoch(),
        start_date INTEGER,
        end_date INTEGER,
        stdout TEXT,
        stderr TEXT)
    """)
    return cnx, cursor

### getter and setter functions ###
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

def setStatus(job_id, status): setValue(job_id, "status", status)
def getStatus(job_id): return getValue(job_id, "status")
def setHost(job_id, host): setValue(job_id, "host", host)
def getHost(job_id): return getValue(job_id, "host")
def setPid(job_id, pid): setValue(job_id, "pid", pid)
def getPid(job_id): return getValue(job_id, "pid")
def setStdOut(job_id, text): setValue(job_id, "stdout", text)
def getStdOut(job_id): return getValue(job_id, "stdout")
def setStdErr(job_id, text): setValue(job_id, "stderr", text)
def getStdErr(job_id): return getValue(job_id, "stderr")
def setStartDate(job_id): setValue(job_id, "start_date", int(time.time()))
def setEndDate(job_id): setValue(job_id, "end_date", int(time.time()))
def getSettings(job_id): return eval(getValue(job_id, "settings"))
def getAppName(job_id): return getValue(job_id, "appname")
def getStrategy(job_id): return getValue(job_id, "strategy")
def isOwner(job_id, owner): return getValue(job_id, "owner") == owner

def addToStderr(job_id, text):
  stderr = getStdErr(job_id)
  if stderr == "": stderr = f"Cumulus: {text}"
  else: stderr += f"\nCumulus: {text}"

### specific functions ###
def createJob(form):
  # connect to the database
  cnx, cursor = connect()
  # status should be PENDING when created, RUNNING when it's started, DONE if it's finished successfully, FAILED if it's finished in error
  # pid should be null if the job has not started yet, or if it's finished
  # host should be the ip address of the vm where it's going to be executed, it could be null if the first available vm is to be picked
  cursor.execute(f"INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?)", form["username"], form["appname"], form["strategy"], form["description"], str(form["settings"]), "PENDING")
  # return the id of the job
  job_id = cursor.lastrowid
  # disconnect
  cnx.close()
  # return the job_id
  return job_id

def getJobDetails(job_id):
  # connect to the database
  cnx, cursor = connect()
  # search the job that corresponds to the id
  cursor.execute("SELECT owner, appname, strategy, description, settings, status, host, creation_date, start_date, end_date, stdout, stderr from jobs WHERE id = ?", job_id)
  # put the results in a dict
  job = {}
  if cursor.arraysize > 0:
    owner, appname, strategy, description, settings, status, host, creation_date, start_date, end_date, stdout, stderr = cursor.fetchone()
    job = {"settings": settings, "strategy": strategy, "description": description, "username": owner, "appname": appname, "status": status, "host": host, "creation_date": creation_date, "start_date": start_date, "end_date": end_date, "stdout": stdout, "stderr": stderr}
  # disconnect and return the job
  cnx.close()
  return job

def getJobToString(job_id):
  # connect to the database
  cnx, cursor = connect()
  # search the job that corresponds to the id
  cursor.execute("SELECT owner, appname, status, host from jobs WHERE id = ?", job_id)
  job = ""
  if cursor.arraysize > 0:
    owner, appname, status, host = cursor.fetchone()
    job = f"Job {job_id}, owner:{owner}, app:{appname}, status:{status}, host:{host}"
  # disconnect and return the string
  cnx.close()
  return job

def getJobStatus(job_id):
  # connect to the database
  cnx, cursor = connect()
  # search the job that corresponds to the id
  cursor.execute("SELECT status, stdout, stderr from jobs WHERE id = ?", job_id)
  # put the results in a dict
  response = "", "", ""
  if cursor.arraysize > 0:
    status, stdout, stderr = cursor.fetchone()
    response = status, stdout, stderr
  # disconnect and return the status with stdout and stderr
  cnx.close()
  return response

def getJobList(host = "*", owner = "*", appname = "*", tag = "*", number = 100):
  # connect to the database
  cnx, cursor = connect()
  # search the jobs that fit the conditions
  results = cursor.execute("SELECT id, owner, appname, status, creation_date from jobs WHERE host LIKE ? AND owner LIKE ? AND appname LIKE ? AND (description LIKE ? OR settings LIKE ?) SORT BY id DESC LIMIT ?", host, owner, appname, tag, tag, number)
  # put the results in a dict
  jobs = []
  for id, owner, appname, status, creation_date in results:
    jobs.append(f"{id}:{status}:{appname}:{owner}:creation_date")
  return jobs

def getJobsPerStatus(status):
  # connect to the database
  cnx, cursor = connect()
  # search the jobs that fit the conditions
  results = cursor.execute("SELECT id from jobs WHERE status = ? SORT BY id ASC", status)
  # return a list of job ids
  return results

def getAliveJobsPerHost(host_name):
  # connect to the database
  cnx, cursor = connect()
  # search the jobs that fit the conditions
  results = cursor.execute("SELECT status from jobs WHERE host = ? AND (status = 'RUNNING' or status = 'PENDING')", host_name)
  # count each type of job
  pending = 0
  running = 0
  for status in results:
    if status == "PENDING": pending += 1
    else: running += 1
  return pending, running
