import logging
import os
import sqlite3
import time

import cumulus_server.libs.cumulus_config as config

logger = logging.getLogger(__name__)

def connect():
  # connect to the database, create it if it does not exist yet
  cnx = sqlite3.connect(config.get("database.file.path"))
  cursor = cnx.cursor()
  # create the main table if it does not exist
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs(
      id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
      owner TEXT NOT NULL,
      app_name TEXT NOT NULL,
      strategy TEXT NOT NULL,
      description TEXT NOT NULL,
      settings TEXT NOT NULL,
      status TEXT NOT NULL,
      host TEXT,
      pid INTEGER,
      creation_date INTEGER,
      start_date INTEGER,
      end_date INTEGER,
      stdout TEXT,
      stderr TEXT,
      job_dir TEXT)
  """)
  return cnx, cursor

### getter and setter functions ###
def set_value(job_id, field, value):
  # connect to the database
  cnx, cursor = connect()
  # TODO test that it does not fail if the job_id does not exist
  cursor.execute(f"UPDATE jobs SET {field} = ? WHERE id = ?", (value, job_id))
  # disconnect
  cnx.close()

def get_value(job_id, field):
  # connect to the database
  cnx, cursor = connect()
  # TODO test that it does not fail if the job_id does not exist
  cursor.execute(f"SELECT {field} FROM jobs WHERE id = ?", (job_id,))
  value = cursor.fetchone() if cursor.arraysize > 0 else ""
  # disconnect and return the value
  cnx.close()
  return value

def set_status(job_id, status): set_value(job_id, "status", status)
def get_status(job_id): return get_value(job_id, "status")
def set_host(job_id, host): set_value(job_id, "host", host)
def get_host(job_id): return get_value(job_id, "host")
def set_pid(job_id, pid): set_value(job_id, "pid", pid)
def get_pid(job_id): return get_value(job_id, "pid")
def set_stdout(job_id, text): set_value(job_id, "stdout", text)
def get_stdout(job_id): return get_value(job_id, "stdout")
def set_stderr(job_id, text): set_value(job_id, "stderr", text)
def get_stderr(job_id): return get_value(job_id, "stderr")
def set_start_date(job_id): set_value(job_id, "start_date", int(time.time()))
def set_end_date(job_id): set_value(job_id, "end_date", int(time.time()))
def get_settings(job_id): return eval(get_value(job_id, "settings"))
def get_app_name(job_id): return get_value(job_id, "app_name")
def get_strategy(job_id): return get_value(job_id, "strategy")
def is_owner(job_id, owner): return get_value(job_id, "owner") == owner
#def set_job_dir(job_id, dir): set_value(job_id, "job_dir", text)
def get_job_dir(job_id): return get_value(job_id, "job_dir")

def add_to_stderr(job_id, text):
  stderr = get_stderr(job_id)
  if stderr == "": stderr = f"Cumulus: {text}"
  else: stderr += f"\nCumulus: {text}"

### specific functions ###
def create_job(form, main_job_dir):
  # connect to the database
  cnx, cursor = connect()
  # status should be PENDING when created, RUNNING when it's started, DONE if it's finished successfully, FAILED if it's finished in error
  # pid should be null if the job has not started yet, or if it's finished
  # host should be the ip address of the vm where it's going to be executed, it could be null if the first available vm is to be picked
  #cursor.execute(f"INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?)", (form["username"], form["app_name"], form["strategy"], form["description"], str(form["settings"]), "PENDING"))
  owner = form["username"]
  app_name = form["app_name"]
  creation_date = int(time.time())
  cursor.execute(f"INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (None, owner, app_name, form["strategy"], form["description"], str(form["settings"]), "PENDING", "", 0, creation_date, None, None, "", "", ""))
  # return the id of the job
  job_id = cursor.lastrowid
  # define the job directory "job_<num>_<user>_<app>_<timestamp>"
  job_dir = f"{main_job_dir}/Job_{job_id}_{owner}_{app_name}_{str(creation_date)}"
  #set_job_dir(job_id, job_dir)
	cursor.execute(f"UPDATE jobs SET job_dir = ? WHERE id = ?", (job_dir, job_id))
  # disconnect
  cnx.close()
  # return the job_id
  return job_id, job_dir

def get_job_details(job_id):
  # connect to the database
  cnx, cursor = connect()
  # search the job that corresponds to the id
  cursor.execute("SELECT owner, app_name, strategy, description, settings, status, host, creation_date, start_date, end_date, stdout, stderr from jobs WHERE id = ?", (job_id,))
  # put the results in a dict
  job = {}
  #if cursor.arraysize > 0:
  #  owner, app_name, strategy, description, settings, status, host, creation_date, start_date, end_date, stdout, stderr = cursor.fetchone()
  #  job = {"settings": settings, "strategy": strategy, "description": description, "username": owner, "app_name": app_name, "status": status, "host": host, "creation_date": creation_date, "start_date": start_date, "end_date": end_date, "stdout": stdout, "stderr": stderr}
	response = cursor.fetchone()
  if response:
    job["settings"] = response[4]
    job["strategy"] = response[2]
    job["description"] = response[3]
    job["username"] = response[0]
    job["app_name"] = response[1]
    job["status"] = response[5]
    job["host"] = response[6]
    job["creation_date"] = response[7]
    job["start_date"] = response[8]
    job["end_date"] = response[9]
    job["stdout"] = response[10]
    job["stderr"] = response[11]
  # disconnect and return the job
  cnx.close()
  return job

def get_job_to_string(job_id):
  # connect to the database
  cnx, cursor = connect()
  # search the job that corresponds to the id
  cursor.execute("SELECT owner, app_name, status, host from jobs WHERE id = ?", (job_id,))
  job = ""
  if cursor.arraysize > 0:
    owner, app_name, status, host = cursor.fetchone()
    job = f"Job {job_id}, owner:{owner}, app:{app_name}, status:{status}, host:{host}"
  # disconnect and return the string
  cnx.close()
  return job

def get_job_status(job_id):
  # connect to the database
  cnx, cursor = connect()
  # search the job that corresponds to the id
  cursor.execute("SELECT status, stdout, stderr from jobs WHERE id = ?", (job_id,))
  # put the results in a dict
  response = "", "", ""
  if cursor.arraysize > 0:
    status, stdout, stderr = cursor.fetchone()
    response = status, stdout, stderr
  # disconnect and return the status with stdout and stderr
  cnx.close()
  return response

def get_job_list(host = "*", owner = "*", app_name = "*", tag = "*", number = 100):
  # connect to the database
  cnx, cursor = connect()
  # search the jobs that fit the conditions
  results = cursor.execute("SELECT id, owner, app_name, status, creation_date from jobs WHERE host LIKE ? AND owner LIKE ? AND app_name LIKE ? AND (description LIKE ? OR settings LIKE ?) ORDER BY id DESC LIMIT ?", (host, owner, app_name, tag, tag, number))
  # put the results in a dict
  jobs = []
  for id, owner, app_name, status, creation_date in results:
    jobs.append(f"{id}:{status}:{app_name}:{owner}:creation_date")
  cnx.close()
  return jobs

def get_jobs_per_status(status):
  # connect to the database
  cnx, cursor = connect()
  # search the jobs that fit the conditions
  results = cursor.execute("SELECT id from jobs WHERE status = ? ORDER BY id ASC", (status,))
  # store the ids
  jobs = []
  for id in results: jobs.append(id)
  cnx.close()
  # return a list of job ids
  return jobs

def get_alive_jobs_per_host(host_name):
  # connect to the database
  cnx, cursor = connect()
  # search the jobs that fit the conditions
  results = cursor.execute("SELECT status from jobs WHERE host = ? AND (status = 'RUNNING' or status = 'PENDING')", (host_name,))
  # count each type of job
  pending = 0
  running = 0
  for status in results:
    if status == "PENDING": pending += 1
    else: running += 1
  cnx.close()
  return pending, running
