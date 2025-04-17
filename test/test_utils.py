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

import libs.cumulus_utils as utils
import os
import shutil

def test_get_all_hosts():
    assert len(utils.get_all_hosts()) == 3

def test_get_host():
    assert utils.get_host("my_second_host").cpu == "16"
    assert utils.get_host("my_fourth_host") == None

def test_is_alive():
    # update the modification time of one pid file
    os.utime("test/pids/my_second_host", None)
    assert utils.is_alive("my_second_host", "909977") == True
    assert utils.is_alive("my_second_host", "12345") == False
    # the pid is in the file, but the file is too old
    assert utils.is_alive("my_third_host", "232050") == False
    assert utils.is_alive("my_third_host", "12345") == False

def test_create_job_directory():
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
    utils.create_job_directory("test_job", form)
    # check the results
    assert os.path.exists("./test/jobs/test_job") == True
    assert os.path.exists("./test/jobs/test_job/temp") == True
    assert os.path.exists("./test/jobs/test_job/.cumulus.settings") == True
    assert os.path.getsize("./test/jobs/test_job/.cumulus.settings") > 1500
    shutil.rmtree("./test/jobs/test_job")

def test_get_size():
    assert utils.get_size("./test/hosts.tsv") == 265
    assert utils.get_size("./test/apps") > 45000

def test_get_raw_file_list():
    assert len(utils.get_raw_file_list()) == 10

def test_delete_raw_file():
    # first copy some files and folders
    raw_file = shutil.copy("./test/raw_test_file.mgf", "./test/data/")
    raw_folder = shutil.copytree("./test/pids", "./test/data/raw_folder.d")
    # make sure they exist
    assert os.path.exists(raw_file) == True
    assert os.path.exists(raw_folder) == True
    # delete them
    utils.delete_raw_file(raw_file)
    utils.delete_raw_file(raw_folder)
    # make sure they are gone
    assert os.path.exists(raw_file) == False
    assert os.path.exists(raw_folder) == False

def test_get_pid_file():
    assert utils.get_pid_file(1).endswith(".cumulus.pid")

def test_get_pid():
    job_dir = os.path.dirname(utils.get_pid_file(1))
    temp_dir = "./test/jobs/job1_complete"
    os.rename(temp_dir, job_dir)
    assert utils.get_pid(1) == 12318
    os.rename(job_dir, temp_dir)

def test_add_to_stderr():
    log_file = "./test/logs/job_1.stderr"
    utils.add_to_stderr(1, "TEST")
    assert(os.path.getsize(log_file) == 15)
    utils.add_to_stderr(1, "TEST")
    assert(os.path.getsize(log_file) == 30)
    os.remove(log_file)
    with open(log_file, "a"):
        os.utime(log_file, None)

def test_get_file_age_in_seconds():
    # this file is older than a day
    assert utils.get_file_age_in_seconds("./test/hosts.tsv") > 86400
    # this file is brand new (created in the previous test, so the value should be 0 or 1)
    assert utils.get_file_age_in_seconds("./test/logs/job_1.stderr") < 3
    # this file does not exist
    assert utils.get_file_age_in_seconds("./test/does_not_exist") == 0
    assert utils.get_file_age_in_seconds(None) == 0

def test_get_zombie_jobs():
    assert len(utils.get_zombie_jobs()) == 6

def test_get_unused_shared_files_older_than():
    assert len(utils.get_unused_shared_files_older_than(86400)) == 5
    # remove the test database
    os.remove("test/cumulus.db")