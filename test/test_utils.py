import cumulus_server.libs.cumulus_utils as utils
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
    assert utils.get_size("./test/apps") == 43692

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