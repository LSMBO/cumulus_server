# Copyright or © or Copr. Alexandre BUREL for LSMBO / IPHC UMR7178 / CNRS (2024)
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

import json
import logging
import os
import sqlite3
import time

import cumulus_server.libs.cumulus_config as config

logger = logging.getLogger(__name__)

def connect():
	# connect to the database, create it if it does not exist yet
	cnx = sqlite3.connect(config.get("database.file.path"), isolation_level = None)
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
			creation_date INTEGER,
			start_date INTEGER,
			end_date INTEGER,
			stdout TEXT,
			stderr TEXT,
			job_dir TEXT)
	""")
	cnx.commit()
	return cnx, cursor

### getter and setter functions ###
def set_value(job_id, field, value):
	# connect to the database
	cnx, cursor = connect()
	# TODO test that it does not fail if the job_id does not exist
	logger.debug(f"UPDATE jobs SET {field} = {value} WHERE id = {job_id}")
	cursor.execute(f"UPDATE jobs SET {field} = ? WHERE id = ?", (value, job_id))
	cnx.commit()
	# disconnect
	cnx.close()

def get_value(job_id, field):
	# connect to the database
	cnx, cursor = connect()
	# TODO test that it does not fail if the job_id does not exist
	cursor.execute(f"SELECT {field} FROM jobs WHERE id = ?", (job_id,))
	value = cursor.fetchone()[0] if cursor.arraysize > 0 else ""
	# disconnect and return the value
	cnx.close()
	return value

def set_status(job_id, status): set_value(job_id, "status", status)
def get_status(job_id): return get_value(job_id, "status")
def set_host(job_id, host): set_value(job_id, "host", host)
def get_host(job_id): return get_value(job_id, "host")
#def set_pid(job_id, pid): set_value(job_id, "pid", pid)
#def get_pid(job_id): return get_value(job_id, "pid")
def set_stdout(job_id, text): set_value(job_id, "stdout", text)
def get_stdout(job_id): return get_value(job_id, "stdout")
def set_stderr(job_id, text): set_value(job_id, "stderr", text)
def get_stderr(job_id): return get_value(job_id, "stderr")
def set_start_date(job_id): set_value(job_id, "start_date", int(time.time()))
def set_end_date(job_id): set_value(job_id, "end_date", int(time.time()))
def get_settings(job_id): return json.loads(get_value(job_id, "settings"))
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
	# status should be PENDING when created, RUNNING when it's started, DONE if it's finished successfully, FAILED if it's finished in error, CANCELLED if user chose to cancel it, ARCHIVED if the job has been cleaned due to old age
	# host should be the ip address of the vm where it's going to be executed, it could be null if the first available vm is to be picked
	owner = form["username"]
	app_name = form["app_name"]
	creation_date = int(time.time())
	# settings are already passed as a stringified json
	cursor.execute(f"INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (None, owner, app_name, form["strategy"], form["description"], form["settings"], "PENDING", "", creation_date, None, None, "", "", ""))
	# return the id of the job
	job_id = cursor.lastrowid
	# define the job directory "job_<num>_<user>_<app>_<timestamp>"
	job_dir = f"{main_job_dir}/Job_{job_id}_{owner}_{app_name}_{str(creation_date)}"
	#set_job_dir(job_id, job_dir)
	cursor.execute(f"UPDATE jobs SET job_dir = ? WHERE id = ?", (job_dir, job_id))
	cnx.commit()
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
	response = cursor.fetchone()
	if response:
		job["settings"] = json.loads(response[4])
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
	response = []
	if cursor.arraysize > 0:
		status, stdout, stderr = cursor.fetchone()
		response.append(status)
		response.append(stdout)
		response.append(stderr)
	# disconnect and return the status with stdout and stderr
	cnx.close()
	return response

# TODO remove this function
#def get_job_list(host = "%", owner = "%", app_name = "%", tag = "%", number = 100):
#	# connect to the database
#	cnx, cursor = connect()
#	# search the jobs that fit the conditions
#	logger.debug(f"SELECT id, owner, app_name, status, creation_date from jobs WHERE host LIKE '{host}' AND owner LIKE '{owner}' AND app_name LIKE '{app_name}' AND (description LIKE '{tag}' OR settings LIKE '{tag}') ORDER BY id DESC LIMIT '{number}'")
#	results = cursor.execute("SELECT id, owner, app_name, status, creation_date from jobs WHERE host LIKE ? AND owner LIKE ? AND app_name LIKE ? AND (description LIKE ? OR settings LIKE ?) ORDER BY id DESC LIMIT ?", (host, owner, app_name, tag, tag, number))
#	# put the results in a dict
#	jobs = []
#	for id, owner, app_name, status, creation_date in results:
#		jobs.append({"id": id, "status": status, "app_name": app_name, "owner": owner, "creation_date": creation_date})
#	cnx.close()
#	return jobs

def get_last_jobs(number = 100):
	# connect to the database
	cnx, cursor = connect()
	# search the jobs that fit the conditions
	logger.debug(f"SELECT id, owner, app_name, status, creation_date from jobs ORDER BY id DESC LIMIT '{number}'")
	results = cursor.execute("SELECT id, owner, app_name, status, creation_date from jobs ORDER BY id DESC LIMIT ?", (number))
	# put the results in a dict
	jobs = []
	for id, owner, app_name, status, creation_date in results:
		jobs.append({"id": id, "status": status, "app_name": app_name, "owner": owner, "creation_date": creation_date})
	cnx.close()
	return jobs

def search_jobs(form) {
	# get the user search parameters
	owner = "%" if form["owner"] == "" else "%" + form["owner"] + "%"
	app_name = "%" if form["app"] == "" else "%" + form["app"] + "%"
	file = "%" if form["file"] == "" else "%" + form["file"] + "%"
	desc = "%" if form["description"] == "" else "%" + form["description"] + "%"
	
	# prepare the part of the request for the status
	statuses = []
	if form["pending"] != None: statuses.append("status = 'PENDING'")
	if form["running"] != None: statuses.append("status = 'RUNNING'")
	if form["done"] != None: statuses.append("status = 'DONE'")
	if form["failedrunning"] != None: statuses.append("status = 'FAILED'")
	if form["cancelled"] != None: statuses.append("status = 'CANCELLED'")
	if form["archived"] != None: statuses.append("status LIKE 'ARCHIVED%'")
	request_status = "" if len(statuses) == 0 or len(statuses) == 6 else "AND (" + " OR ".join(statuses) + ")"
	
	# prepare the part of the request for the date
	date_field = form["date"]
	date_from = 0 if form["from"] == "" else time.mktime(datetime.datetime.strptime(form["from"], "%Y-%m-%d").timetuple())
	date_to = int(time.time())) if form["to"] == "" else time.mktime(datetime.datetime.strptime(form["to"], "%Y-%m-%d").timetuple())
	request_date = f"AND {date_field} BETWEEN {date_from} AND {date_to}"
	
	# connect to the database
	cnx, cursor = connect()
	results = cursor.execute(f"SELECT id, owner, app_name, status, creation_date from jobs WHERE owner LIKE ? AND app_name LIKE ? AND description LIKE ? AND settings LIKE ? {request_status} {request_date} ORDER BY id DESC LIMIT ?", (owner, app_name, desc, file, form["number"]))
	# put the results in a dict
	jobs = []
	for id, owner, app_name, status, creation_date in results:
		jobs.append({"id": id, "status": status, "app_name": app_name, "owner": owner, "creation_date": creation_date})
	cnx.close()
	return jobs
}

def get_jobs_per_status(status):
	# connect to the database
	cnx, cursor = connect()
	# search the jobs that fit the conditions
	results = cursor.execute("SELECT id from jobs WHERE status = ? ORDER BY id ASC", (status,))
	# store the ids
	jobs = []
	for id, in results: jobs.append(id)
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
	for status, in results:
		if status == "PENDING": pending += 1
		else: running += 1
	cnx.close()
	return pending, running

def delete_job(job_id):
	# connect to the database
	cnx, cursor = connect()
	# delete the job
	cursor.execute(f"DELETE FROM jobs WHERE id = ?", (job_id,))
	cnx.commit()
	# disconnect
	cnx.close()
