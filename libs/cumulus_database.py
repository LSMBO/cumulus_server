# Copyright or © or Copr. Alexandre BUREL for LSMBO / IPHC UMR7178 / CNRS (2025)
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
import sqlite3
import time
from datetime import datetime

import libs.cumulus_config as config
import libs.cumulus_apps as apps

logger = logging.getLogger(__name__)

def connect():
	"""
	Establishes a connection to the SQLite database specified in the configuration.
	This function does not check if the database file exists; it simply attempts to connect
 	to the database file specified in the configuration. The database must have been 
	initialized at the start of the execution.

	Returns:
		tuple: A tuple containing the SQLite connection object and the cursor object.
	"""
	# connect to the database, create it if it does not exist yet
	cnx = sqlite3.connect(config.get("database.file.path"), isolation_level = None, timeout = 30, check_same_thread = False)
	cursor = cnx.cursor()
	return cnx, cursor

def add_column(cnx, cursor, column_name, column_type):
	# the database may already exist, but we want to ensure that the following columns are present
	cursor.execute(f"SELECT COUNT(*) FROM pragma_table_info('jobs') WHERE name = '{column_name}'")
	response = cursor.fetchone()
	if response[0] == 0:
		# add the start_after_id column if it does not exist
		cursor.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_type}")
		cnx.commit()
		logger.info(f"Column '{column_name}' has been added to the database.")

def initialize_database():
	"""
	Initializes the database by connecting to it and ensuring the 'jobs' table exists.
	This function is typically called at the start of the application to set up the
	database environment. If the database file does not exist, it will be created. 
	Also ensures that the 'jobs' table exists in the database, creating it if necessary.

	Returns:
	None
	"""
	# connect to the database, create it if it does not exist yet
	cnx, cursor = connect()
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
			job_dir TEXT,
			start_after_id INTEGER,
			workflow_name TEXT,
			last_modified INTEGER)
	""")
	cnx.commit()
	# the database may already exist, but we want to ensure that the following columns are present
	add_column(cnx, cursor, "start_after_id", "INTEGER")
	add_column(cnx, cursor, "workflow_name", "TEXT")
	add_column(cnx, cursor, "last_modified", "INTEGER")
	# close the connection
	cnx.close()
	logger.info("Database initialized successfully.")

def create_job(form):
	"""
	Creates a new job entry in the database with the provided form data.

	Args:
		form (dict): A dictionary containing job parameters. Expected keys include:
			- "username": The owner of the job.
			- "app_name": The name of the application to run.
			- "workflow_name": (optional) The name of the workflow to run (null if it's a single app).
			- "strategy": The execution strategy for the job.
			- "description": A description of the job.
			- "settings": A JSON string of job settings.
			- "start_after_id": (optional) The ID of the previous job if the job is part of a workflow (if missing, it's a standard job).

	Returns:
		tuple: A tuple containing:
			- job_id (int): The ID of the newly created job.
			- job_dir_name (str): The name of the directory assigned to the job.

	Raises:
		KeyError: If required keys are missing from the form.
		Exception: If database operations fail.

	Notes:
		- The job is created with status "PENDING".
		- The job directory is named using the job ID, owner, app name, and creation timestamp.
	"""
	# connect to the database
	cnx, cursor = connect()
	# status should be PENDING when created, RUNNING when it's started, DONE if it's finished successfully, FAILED if it's finished in error, CANCELLED if user chose to cancel it, ARCHIVED if the job has been cleaned due to old age
	# host should be the ip address of the vm where it's going to be executed, it could be null if the first available vm is to be picked
	owner = form["username"]
	app_name = form["app_name"]
	workflow_name = form["workflow_name"] if "workflow_name" in form else None
	creation_date = int(time.time())
	start_after_id = form["start_after_id"] if "start_after_id" in form else None
	# settings are already passed as a stringified json
	cursor.execute(f"INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (None, owner, app_name, form["strategy"], form["description"], form["settings"], "PENDING", "", creation_date, None, None, "", "", "", start_after_id, workflow_name, 0))
	# return the id of the job
	job_id = cursor.lastrowid
	# define the job directory "job_<num>_<user>_<app>_<timestamp>"
	job_dir_name = f"Job_{job_id}_{owner}_{app_name}_{str(creation_date)}"
	job_dir = f"{config.JOB_DIR}/{job_dir_name}"
	cursor.execute(f"UPDATE jobs SET job_dir = ? WHERE id = ?", (job_dir, job_id))
	cnx.commit()
	# disconnect
	cnx.close()
	# return the job_id and the name of its directory
	return job_id, job_dir_name

def get_value(job_id, field):
	"""
	Retrieve the value of a specified field from the 'jobs' table for a given job ID.

	Args:
		job_id (int): The ID of the job to look up.
		field (str): The name of the field to retrieve from the 'jobs' table.

	Returns:
		Any: The value of the specified field for the given job ID, or an empty string if the job does not exist or the field is not found.

	Note:
		Calls the function 'connect' from sqlite3 that returns a tuple (connection, cursor).
		The function currently does not handle exceptions or SQL injection risks related to the `field` parameter.
	"""
	# connect to the database
	cnx, cursor = connect()
	# TODO test that it does not fail if the job_id does not exist
	cursor.execute(f"SELECT {field} FROM jobs WHERE id = ?", (job_id,))
	value = ""
	if cursor.arraysize > 0:
		response = cursor.fetchone()
		if response is not None: value = response[0]
	# disconnect and return the value
	cnx.close()
	return value

def set_value(job_id, field, value):
	"""
	Updates the specified field of a job record in the 'jobs' table with a new value.

	Args:
		job_id (int): The ID of the job to update.
		field (str): The name of the field/column to update.
		value (Any): The new value to set for the specified field.

	Raises:
		Exception: If the database operation fails.

	Note:
		Calls the function 'connect' from sqlite3 that returns a tuple (connection, cursor).
		The function uses parameterized queries for the value and job_id, but the field name is interpolated directly into the SQL statement.
		Ensure that the 'field' parameter is validated to prevent SQL injection.
	"""
	# connect to the database
	cnx, cursor = connect()
	logger.debug(f"UPDATE jobs SET {field} = {value} WHERE id = {job_id}")
	cursor.execute(f"UPDATE jobs SET {field} = ? WHERE id = ?", (value, job_id))
	cnx.commit()
	# disconnect
	cnx.close()

def get_workflow_parent_id(job_id):
	"""
	Retrieves the first job id for the workflow of the given job.
	It uses the start_after_id field to find the parent job that starts after the specified job ID.

	Args:
		job_id (int): The ID of the job for which to find the parent job in the workflow.

	Returns:
		int: The first job id for which there is no start_after_id.
	"""
	# start with the given job_id, it's possible that this id is the parent
	parent_job_id = job_id
	# connect to the database
	cnx, cursor = connect()
	while True:
		# search the job that corresponds to the id
		cursor.execute("SELECT start_after_id FROM jobs WHERE id = ?", (parent_job_id,))
		if cursor.arraysize == 0: break # the job should exist, but if it does not, we stop here
		results = cursor.fetchone()
		if results == None or results[0] == None: break # if the job has no parent, we stop here (real stop condition)
		if results == "" or results[0] == "": break # if the job has no parent, we stop here (real stop condition)
		parent_job_id = results[0]
	cnx.close()
	return parent_job_id

def get_associated_jobs(job_id):
	"""
	Retrieve all job IDs associated with the same workflow as the given job.
	If the specified job is part of a workflow, this function returns a list of job IDs
	representing the sequence of jobs in that workflow, starting from the parent job and
	following the chain of jobs linked by the `start_after_id` field. If the job is not
	part of a workflow, the returned list contains only the given job ID.
	Args:
		job_id (int): The ID of the job for which to retrieve associated jobs.
	Returns:
		list[int]: A list of job IDs in the workflow, or a list containing only the given job ID
		if it is not part of a workflow.
	"""
	# if the job has no start_after_id, it is not part of a workflow or it's the first job in a workflow
	parent_job_id = get_workflow_parent_id(job_id)
	# prepare the list of ids
	ids = [parent_job_id]
	# connect to the database
	cnx, cursor = connect()
	next_id = parent_job_id
	while True:
		# search the job that corresponds to the id
		cursor.execute("SELECT id FROM jobs WHERE start_after_id = ?", (next_id,))
		if cursor.arraysize == 0: break # if no job is found, we stop here (real stop condition)
		results = cursor.fetchone()
		if results == None: break
		next_id = results[0]
		ids.append(next_id)
	cnx.close()
	return ids

def set_status(job_id, status): set_value(job_id, "status", status)
def get_status(job_id): return get_value(job_id, "status")
def set_start_date(job_id): set_value(job_id, "start_date", int(time.time()))
def set_end_date(job_id):
	# if the job represents a workflow, set the host to all other jobs
	# this allows to clean all the jobs in a workflow at once in the cleaning daemon
	end = int(time.time())
	for id in get_associated_jobs(job_id): set_value(id, "end_date", end)
def get_settings(job_id): return json.loads(get_value(job_id, "settings"))
def get_app_name(job_id): return get_value(job_id, "app_name")
def get_strategy(job_id): return get_value(job_id, "strategy")
def set_strategy(job_id, strategy):
	# if the job represents a workflow, set the strategy to all other jobs
	# for id in get_associated_jobs(job_id): set_value(job_id, "strategy", strategy)
	for id in get_associated_jobs(job_id): set_value(id, "strategy", strategy)
def is_owner(job_id, owner): return get_value(job_id, "owner") == owner
def get_job_dir(job_id): return get_value(job_id, "job_dir")
def set_job_dir(job_id, job_dir): set_value(job_id, "job_dir", job_dir)
def get_last_modified(job_id): return get_value(job_id, "last_modified")
def set_last_modified(job_id, timestamp): set_value(job_id, "last_modified", timestamp)

def check_job_existency(job_id):
	"""
	Checks if a job with the specified job_id exists in the 'jobs' table of the database.

	Args:
		job_id (int): The ID of the job to check for existence.

	Returns:
		bool: True if a job with the given job_id exists, False otherwise.
	"""
	# connect to the database
	cnx, cursor = connect()
	# search the job that corresponds to the id
	cursor.execute("SELECT COUNT(*) from jobs WHERE id = ?", (job_id,))
	# return true if there is a match
	response = cursor.fetchone()
	# disconnect
	cnx.close()
	return response[0] > 0

def get_job_to_string(job_id):
	"""
	Retrieve a string representation of a job from the database by its ID.

	Args:
		job_id (int): The unique identifier of the job to retrieve.

	Returns:
		str: A formatted string containing the job's ID, owner, application name, status, and host.
			 Returns an empty string if no job is found with the given ID.
	"""
	# differentiate between a job and a workflow job
	job_ids = get_associated_jobs(job_id)
	tag = "Job" if len(job_ids) == 1 else "Workflow job"
	# connect to the database
	cnx, cursor = connect()
	# search the job that corresponds to the id
	cursor.execute("SELECT owner, app_name, status, strategy FROM jobs WHERE id = ?", (job_id,))
	job = ""
	if cursor.arraysize > 0:
		owner, app_name, status, strategy = cursor.fetchone()
		job = f"{tag} {job_id}, owner:{owner}, app:{app_name}, status:{status}, strategy:{strategy}"
	# disconnect and return the string
	cnx.close()
	return job

def get_merged_settings(job_id):
	"""
	Searches for the settings of all the jobs related to the given job
	This is useful for workflows, we need to return the settings of the entire workflow, and not just one job
	
	Args:
		job_id (int): The job ID to use as a reference for searching and retrieving related jobs.
	
	Returns:
		list: a dictionary with the job_ids and the corresponding settings
	
	Notes:
		if job_id does not corresponds to a workflow, the dictionary will only contain one entry
	"""
	# prepare the map
	settings_set = {}
	# get all the ids to search for
	job_ids = get_associated_jobs(job_id)
	# connect to the database
	cnx, cursor = connect()
	# search for all the settings
	results = cursor.execute(f"SELECT id, settings from jobs WHERE id IN ({", ".join(["?"] * len(job_ids))}) ORDER BY id ASC", (job_ids))
	for id, settings in results:
		settings_set[id] = json.loads(settings)
	# close the connection
	cnx.close()
	return settings_set

# def list_jobs(current_job_id, number = 100, owner = "%", app_name = "%", description = "%", statuses = [], date_field = "creation_date", date_from = 0, date_to = int(time.time()), file = ""):
def list_jobs(current_job_id, number = 100, owner = "%", app_name = "%", description = "%", statuses = [], date_field = "creation_date", date_from = None, date_to = None, file = ""):
	"""
	Search for jobs in the database based on various filtering criteria.

	Args:
		job_id (int): The job ID to use as a reference for searching and retrieving related jobs.
		number (int, optional): The maximum number of jobs to retrieve. Defaults to 100.
		owner (str, optional): The owner of the job(s) to search for. Supports SQL LIKE patterns. Defaults to "%".
		app_name (str, optional): The application name associated with the job(s). Supports SQL LIKE patterns. Defaults to "%".
		description (str, optional): The description of the job(s). Supports SQL LIKE patterns. Defaults to "%".
		statuses (list, optional): List of status conditions to filter jobs. If empty or contains 6 elements, no status filtering is applied. Defaults to [].
		date_field (str, optional): The name of the date field to filter on (e.g., "creation_date"). Defaults to "creation_date".
		date_from (int, optional): The start of the date range (as a Unix timestamp). Defaults to 0.
		date_to (int, optional): The end of the date range (as a Unix timestamp). Defaults to the current time.
		file (str, optional): File filter (not used in SQL filtering). Defaults to "".

	Returns:
		list: A list of dictionaries, each representing a job with its details.

	Notes:
		- The function retrieves jobs matching the specified filters, handling workflows and job dependencies.
		- If filtering by files, additional post-processing is performed since file filtering is not handled in SQL.
		- The function ensures that the job with the specified current_job_id has full details.
	"""
	# prepare parts of the SQL request
	request_status = "" if len(statuses) == 0 or len(statuses) == 6 else "AND (" + " OR ".join(statuses) + ")"
	# request_date = f"AND {date_field} BETWEEN {date_from} AND {date_to}"
	request_date = ""
	if date_from is not None and date_from != "": request_date += f" AND {date_field} >= {date_from}"
	if date_to is not None and date_to != "": request_date += f" AND {date_field} <= {date_to}"
	# connect to the database
	cnx, cursor = connect()
	# prepare the list of jobs to return
	jobs = []
	# prepare a variable to hold the position of the job with id job_id
	job_index = None
	# make the search
	# cursor.execute(f"SELECT id, owner, app_name, status, strategy, description, settings, host, creation_date, start_date, end_date, stdout, stderr, job_dir, start_after_id, workflow_name FROM jobs WHERE owner LIKE ? AND app_name LIKE ? AND description LIKE ? {request_status} {request_date} ORDER BY id DESC LIMIT ?", (owner, app_name, description, number))
	cursor.execute(f"SELECT id, owner, app_name, status, strategy, description, settings, host, creation_date, start_date, end_date, job_dir, start_after_id, workflow_name FROM jobs WHERE owner LIKE ? AND app_name LIKE ? AND description LIKE ? {request_status} {request_date} ORDER BY id DESC LIMIT ?", (owner, app_name, description, number))
	# loop until we have the expected amount of jobs in the array
	nb_jobs = 0
	while len(jobs) < number:
		records = cursor.fetchmany(number)
		if len(records) == 0: break
		# for id, owner, app_name, status, strategy, description, settings, host, creation_date, start_date, end_date, stdout, stderr, job_dir, start_after_id, workflow_name in records:
		for id, owner, app_name, status, strategy, description, settings, host, creation_date, start_date, end_date, job_dir, start_after_id, workflow_name in records:
			# convert the settings from string to json
			settings = json.loads(settings)
			# filter by file here, so we can use a specific function for each app
			if file == "" or apps.is_in_required_files(job_dir, app_name, settings, file):
				# the current job should be more detailed
				if id == current_job_id:
					# store the index of the job, we will add the settings later
					job_index = len(jobs)
					# stdout and stderr for old jobs used to be kept in the database
					# if stdout == "": stdout = apps.get_stdout_content(id)
					# if stderr == "": stderr = apps.get_stderr_content(id)
					log = apps.get_log_file_content(id)
					# store as many information as possible, except for the settings
					# jobs.append({"id": id, "owner": owner, "app_name": app_name, "status": status, "strategy": strategy, "description": description, "settings": "", "host": host, "creation_date": creation_date, "start_date": start_date, "end_date": end_date, "stdout": stdout, "stderr": stderr, "start_after_id": start_after_id, "workflow_name": workflow_name, "files": apps.get_file_list(job_dir)})
					# jobs.append({"id": id, "owner": owner, "app_name": app_name, "status": status, "strategy": strategy, "description": description, "settings": "", "host": host, "creation_date": creation_date, "start_date": start_date, "end_date": end_date, "log": log, "start_after_id": start_after_id, "workflow_name": workflow_name, "files": apps.get_file_list(job_dir)})
					jobs.append({"id": id, "owner": owner, "app_name": app_name, "status": status, "strategy": strategy, "description": description, "settings": "", "host": host, "creation_date": creation_date, "start_date": start_date, "end_date": end_date, "log": log, "start_after_id": start_after_id, "workflow_name": workflow_name, "files": apps.get_output_file_list(job_dir)})
				# for other jobs, return what is required for the sidebar
				else:
					jobs.append({"id": id, "owner": owner, "app_name": app_name, "status": status, "host": host, "creation_date": creation_date, "end_date": end_date, "start_after_id": start_after_id, "workflow_name": workflow_name})
			# do not continue if we have enough results
			if len(jobs) == number: break
			# do not continue if no new jobs have been added (to avoid infinite loops)
			if len(jobs) == nb_jobs: break
			nb_jobs = len(jobs)
	cnx.close()
	# search for the complete settings of the current job, it should be a map of [job_id, settings]
	if job_index is not None: jobs[job_index]["settings"] = get_merged_settings(current_job_id)
	# return the final list of jobs
	return jobs

def get_last_jobs(job_id, number = 100):
	"""
	Retrieve the most recent jobs associated with a given job ID.

	Args:
		job_id (Any): The identifier of the job to search for.
		number (int, optional): The maximum number of recent jobs to retrieve. Defaults to 100.

	Returns:
		list: A list of job records matching the given job ID, limited to the specified number.
	"""
	return list_jobs(job_id, number)

def search_jobs(form):
	# get the user search parameters
	current_job_id = int(form["current_job_id"])
	owner = "%" if form["owner"] == "" else "%" + form["owner"] + "%"
	app_name = "%" if form["app"] == "" or form["app"] == "all" else "%" + form["app"] + "%"
	desc = "%" if form["description"] == "" else "%" + form["description"] + "%"
	number = 100 if form["number"] == "" else form["number"]
	file = form["file"]
	# prepare the part of the request for the status
	statuses = []
	if "pending" in form: statuses.append("status = 'PENDING'")
	if "preparing" in form: statuses.append("status = 'PREPARING'")
	if "running" in form: statuses.append("status = 'RUNNING'")
	if "done" in form: statuses.append("status = 'DONE'")
	if "failed" in form: statuses.append("status = 'FAILED'")
	if "cancelled" in form: statuses.append("status = 'CANCELLED'")
	if "archived" in form: statuses.append("status LIKE 'ARCHIVED%'")
	# prepare the part of the request for the date
	date_field = form["date"]
	date_from = 0 if form["from"] == "" else time.mktime(datetime.strptime(form["from"], "%Y-%m-%d").timetuple())
	date_to = int(time.time()) if form["to"] == "" else time.mktime(datetime.strptime(form["to"], "%Y-%m-%d").timetuple())
	# call the list_jobs function to retrieve the jobs
	return list_jobs(current_job_id, number, owner, app_name, desc, statuses, date_field, date_from, date_to, file)

def get_jobs_per_status(status):
	"""
	Retrieve a list of job IDs from the database that match the specified status.
	This function is used when we need to know all the running jobs, pending jobs, etc.

	Args:
		status (str): The status to filter jobs by.

	Returns:
		list: A list of job IDs (int) that have the specified status.
	"""
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

def delete_job(job_id):
	"""
	Deletes a job from the database and removes its associated log files.
	If the job is part of a workflow, the same is done for all jobs in the workflow.

	Args:
		job_id (int): The unique identifier of the job to be deleted.

	Side Effects:
		- Removes the job entry from the 'jobs' table in the database.
		- Deletes the standard output and standard error log files associated with the job, if they exist.

	Raises:
		Any exceptions raised by the database connection, execution, or file operations will propagate.
	"""
	# get all the jobs in case this is a workflow job
	job_ids = get_associated_jobs(job_id)
	# connect to the database
	cnx, cursor = connect()
	# delete all the jobs
	for id in job_ids:
		# delete the job
		cursor.execute(f"DELETE FROM jobs WHERE id = ?", (id,))
		cnx.commit()
	# disconnect
	cnx.close()

def set_fake_creation_date(job_id, seconds_to_add = -86400):
	"""
	Sets a fake creation date for a job by adding a specified number of seconds to its current creation date.
	This function is only used for testing purposes to manipulate the creation date of a job.

	Args:
		job_id (int): The ID of the job whose creation date will be modified.
		seconds_to_add (int, optional): The number of seconds to add to the current creation date. 
			Defaults to -86400 (subtracts one day).

	Raises:
		Exception: If database connection or update fails.

	Note:
		This function connects to the database, updates the 'creation_date' field for the specified job,
		and commits the change.
	"""
	# connect to the database
	cnx, cursor = connect()
	# get the current creation date for the job
	creation_date = int(get_value(job_id, "creation_date"))
	# change the date
	creation_date = creation_date + seconds_to_add
	# set the new creation date
	cursor.execute(f"UPDATE jobs SET creation_date = ? WHERE id = ?", (creation_date, job_id))
	cnx.commit()
	# disconnect
	cnx.close()

def get_ended_jobs_older_than(max_age_seconds):
	"""
	Retrieve jobs from the database that have ended and are older than a specified age.

	Args:
		max_age_seconds (int): The minimum age in seconds a job must be (since its creation date) to be included in the results.

	Returns:
		list of tuple: A list of tuples, each containing (job_id, status, job_dir) for jobs that:
			- Have a creation date older than `max_age_seconds` seconds,
			- Are not in an 'ARCHIVE_%' status,
			- Are not in 'PENDING' or 'RUNNING' status.
	"""
	# connect to the database
	cnx, cursor = connect()
	# search the jobs that fit the conditions
	# results = cursor.execute("SELECT id, status, job_dir FROM jobs WHERE unixepoch() - creation_date > ? AND status NOT LIKE 'ARCHIVE_%' AND status != 'PENDING' AND status != 'RUNNING'", (max_age_seconds,))
	results = cursor.execute("SELECT id, status, job_dir FROM jobs WHERE unixepoch() - creation_date > ? AND status NOT LIKE 'ARCHIVE_%' AND status != 'PENDING' AND status != 'PREPARING' AND status != 'RUNNING'", (max_age_seconds,))
	# store the ids
	jobs = []
	# for job_id, job_dir in results: jobs.append({"job_id": job_id, "job_dir": job_dir})
	for job_id, status, job_dir in results: jobs.append((job_id, status, job_dir))
	cnx.close()
	# return a list of job ids and job directories
	return jobs

def is_file_in_use(file):
	"""
	Checks if a given file is currently in use by any job with status 'RUNNING' or 'PENDING' in the database.

	Args:
		file (str): The path or identifier of the file to check.

	Returns:
		bool: True if the file is required by any running or pending job, False otherwise.

	Raises:
		Any exceptions raised by the database connection or query execution.
	"""
	# connect to the database
	cnx, cursor = connect()
	# search the jobs that are RUNNING or PENDING
	# results = cursor.execute("SELECT app_name, settings, job_dir from jobs WHERE status = 'RUNNING' or status = 'PENDING'")
	results = cursor.execute("SELECT app_name, settings, job_dir from jobs WHERE status = 'RUNNING' or status = 'PREPARING' or status = 'PENDING'")
	# parse the results
	is_used = False
	for app_name, settings, job_dir in results:
		if apps.is_file_required(job_dir, app_name, json.loads(settings), file):
			is_used = True
			break
	# disconnect
	cnx.close()
	return is_used

def get_currently_running_strategies():
	"""
	Retrieve a list of job strategies from the database that are currently running.

	Returns:
		list: A list of strategies (str) that are currently associated with jobs in 'RUNNING' status.
	"""
	# connect to the database
	cnx, cursor = connect()
	# search the jobs that fit the conditions
	# results = cursor.execute("SELECT strategy from jobs WHERE status = 'RUNNING' ORDER BY id ASC")
	results = cursor.execute("SELECT strategy from jobs WHERE status = 'RUNNING' OR status = 'PREPARING' ORDER BY id ASC")
	# store the ids
	strategies = []
	for strategy, in results: strategies.append(strategy)
	cnx.close()
	# return a list of strategies
	return strategies

def pause_preparing_jobs():
	"""
	This function is called only when the main process is stopped.
	The jobs that are currently running should be safe, but the jobs who are in PREPARING status will be impacted.
	To avoid that, we put them in PAUSED status, so we can restart them automatically at the next start of the main process.
	"""
	# connect to the database
	cnx, cursor = connect()
	logger.debug(f"UPDATE jobs SET {field} = {value} WHERE id = {job_id}")
	cursor.execute(f"UPDATE jobs SET status = 'PAUSED' WHERE status = 'PREPARING'")
	cnx.commit()
	# disconnect
	cnx.close()
