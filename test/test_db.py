import cumulus_server.libs.cumulus_config as config
import cumulus_server.libs.cumulus_database as db
import json
import os
import re

def test_db_connect():
    # get the test database file path
    db_path = config.get("database.file.path")
    # the database should not exist yet
    if os.path.isfile(db_path): os.remove(db_path)
    # connect to the database
    cnx, _ = db.connect()
    # the database should now exist
    assert os.path.isfile(db_path)
    # close the database (the file will not be deleted)
    cnx.close()

def test_create_job():
    # get settings as text
    settings = ""
    with open("test/jobs/job1.settings", 'r') as xml:
        settings = xml.read().replace("\n", "")
    # create a fake POST form
    form = {
        "username": "test.user",
        "app_name": "diann_2.0",
        "strategy": "first_available",
        "description": "",
        "settings": settings
    }
    # call the function
    job_id, job_dir_name = db.create_job(form)
    # check the results
    assert job_id == 1
    assert re.search("^Job_1_test.user_diann_2.0_\\d+$", job_dir_name) != None
    # create some other jobs for later tests
    for i in range(4):
        db.create_job(form)

def test_get_value():
    assert db.get_value(1, "strategy") == "first_available"

def test_set_value():
    db.set_value(1, "strategy", "best_cpu")
    assert db.get_value(1, "strategy") == "best_cpu"

def test_get_status():
    assert db.get_status(1) == "PENDING"

def test_set_status():
    db.set_status(1, "FAILED")
    assert db.get_value(1, "status") == "FAILED"

def test_get_host():
    assert db.get_host(1) == ""

def test_set_host():
    db.set_host(1, "my_test_host")
    assert db.get_value(1, "host") == "my_test_host"

def test_set_start_date():
    assert db.get_value(1, "start_date") == None
    db.set_start_date(1)
    assert db.get_value(1, "start_date") > 0

def test_set_end_date():
    assert db.get_value(1, "end_date") == None
    db.set_end_date(1)
    assert db.get_value(1, "end_date") > 0

def test_get_settings():
    # get settings as text
    settings = ""
    with open("test/jobs/job1.settings", 'r') as xml:
        settings = xml.read().replace("\n", "")
    # compare with settings from db
    assert db.get_settings(1) == json.loads(settings)

def test_get_app_name():
    assert db.get_app_name(1) == "diann_2.0"

def test_get_strategy():
    assert db.get_strategy(1) == "best_cpu"

def test_set_strategy():
    db.set_strategy(1, "best_ram")
    assert db.get_value(1, "strategy") == "best_ram"

def test_is_owner():
    assert db.is_owner(1, "test.user") == True
    assert db.is_owner(1, "prod.user") == False

def test_get_job_dir():
    job_dir = db.get_job_dir(1)
    assert re.search("Job_1_test.user_diann_2.0_\\d+$", job_dir) != None

def test_check_job_existency():
    assert db.check_job_existency(1)
    assert not db.check_job_existency(7)

def test_get_job_to_string():
    assert db.get_job_to_string(1) == "Job 1, owner:test.user, app:diann_2.0, status:FAILED, host:my_test_host"

def test_get_last_jobs():
    jobs = db.get_last_jobs(1)
    assert len(jobs) == 5
    assert jobs[4]["id"] == 1
    assert jobs[4]["owner"] == "test.user"
    assert "strategy" not in jobs[1]

def test_search_jobs():
    jobs = db.search_jobs({"current_job_id": 1, "owner": "test.user", "app": "", "description": "", "number": "", "FAILED": "on", "date": "start_date", "from": "", "to": "", "file": ""})
    assert len(jobs) == 1
    assert jobs[0]["id"] == 1

def test_get_jobs_per_status():
    assert db.get_jobs_per_status("PENDING") == [2, 3, 4, 5]
    assert db.get_jobs_per_status("FAILED") == [1]

def test_get_alive_jobs_per_host():
    assert db.get_alive_jobs_per_host("my_test_host") == (0, 0)
    assert db.get_alive_jobs_per_host("") == (4, 0)

def test_delete_job():
    db.delete_job(4)
    assert not db.check_job_existency(4)
