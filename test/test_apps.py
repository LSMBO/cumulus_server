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

import libs.cumulus_config as config
import libs.cumulus_apps as apps
import json
import xml.etree.ElementTree as ET

# load the test config file before running the tests
config.load("test/cumulus.conf")
config.init(False)

def get_settings(file):
    settings = ""
    with open(file, 'r') as xml:
        settings = xml.read().replace("\n", "")
    return json.loads(settings)

def test_get_app_list():
    assert len(apps.get_app_list("test/apps")) == 3

def test_is_finished_ok():
    stdout = ""
    with open("test/logs/diann_1.9.2-ok.log.txt", 'r') as xml:
        stdout = xml.read()
    assert apps.is_finished("diann_1.9.1", stdout) == True

def test_is_finished_ko():
    stdout = ""
    with open("test/logs/diann_1.9.2-ko.log.txt", 'r') as xml:
        stdout = xml.read()
    assert apps.is_finished("diann_1.9.1", stdout) == False

def test_get_file_path_raw():
    assert apps.get_file_path("test", "D:/Projets/DiaNN/test/TP19970FD_Slot1-01_1_20914.d", "true") == "./test/data/TP19970FD_Slot1-01_1_20914.d"

def test_get_file_path_raw():
    assert apps.get_file_path("test", "D:/Projets/DiaNN/test/homosapiens_uniprot.fasta", "false") == "test/homosapiens_uniprot.fasta"

def test_get_all_files_to_convert_to_mzml():
    settings = get_settings("test/jobs/raw2mzml.settings")
    # 95 raw files but 5 of them already exist in the data folder as mzML files
    assert len(apps.get_all_files_to_convert_to_mzml("job_dir", "diann_2.0", settings)) == 90

def test_get_all_files_in_settings():
    settings = get_settings("test/jobs/raw2mzml.settings")
    assert len(apps.get_all_files_in_settings("job_dir", "diann_2.0", settings, False)) == 96
    assert len(apps.get_all_files_in_settings("job_dir", "diann_2.0", settings, True)) == 96

def are_all_files_transfered_complete():
    # all files are transfered
    settings = get_settings("test/jobs/job1.settings")
    assert apps.are_all_files_transfered("test/job1_complete", "diann_2.0", settings) == True

def are_all_files_transfered_incomplete():
    # the rsync file is missing, indicating that all files have not been transfered yet
    settings = get_settings("test/jobs/job1.settings")
    assert apps.are_all_files_transfered("test/job1_incomplete", "diann_2.0", settings) == False

def are_all_files_transfered_complete_but_nok():
    # the rsync file is present but the files are not all transfered
    settings = get_settings("test/jobs/job2.settings")
    assert apps.are_all_files_transfered("test/job2_complete_but_nok", "diann_2.0", settings) == False

def test_replace_in_command():
    assert apps.replace_in_command("--mass-acc-ms1 %value%", "%value%", "10.0") == "--mass-acc-ms1 10.0"

def test_replace_in_command_default():
    assert apps.replace_in_command("--mass-acc-ms1 %value%", "%value2%", "10.0") == "--mass-acc-ms1 %value%"

def test_get_param_command_line():
    # list all apps
    all_apps = apps.get_app_list("test/apps")
    # extract a param from the xml of one app
    root = ET.fromstring(all_apps["diann_2.0"])
    # get from root the first "number" tag (should be missed-cleavages)
    param = root.find(".//number")
    # get the settings of a job
    settings = get_settings("test/jobs/job1.settings")
    # test the function
    assert apps.get_param_command_line(param, settings, "job_dir") == "--missed-cleavages 1"

def test_get_command_line():
    # get the settings of a job
    settings = get_settings("test/jobs/job1.settings")
    # get the full command line
    cmd = apps.get_command_line("diann_2.0", "test/job1_complete", settings, 16, "output_dir")
    assert cmd == "/storage/share/diann-2.0/diann-linux --temp 'temp' --threads 15 --out 'output_dir/report.parquet' --f './test/data/AT2377PAP.mzML' --f './test/data/AT2378PAP.mzML' --f './test/data/AT2379PAP.mzML' --f './test/data/AT2381PAP.mzML' --f './test/data/AT2382PAP.mzML' --lib '' --fasta-search --predictor --gen-spec-lib --fasta 'Human_pSP_CMO_20190213.fasta' --cut 'K*,R*' --missed-cleavages 1 --min-pep-len 7 --max-pep-len 30 --min-pr-charge 1 --max-pr-charge 4 --min-pr-mz 300 --max-pr-mz 1800 --min-fr-mz 200 --max-fr-mz 1800 --pg-level 1 --var-mods 5 --unimod4 --var-mod UniMod:35,15.994915,M --var-mod UniMod:1,42.010565,*n --mass-acc-ms1 5.0 --mass-acc 15.0 --window 10 --reanalyse --peptidoforms --smart-profiling --matrices --qvalue 1.0 --verbose 1"

def test_generate_script():
    # get the settings of a job
    settings = get_settings("test/jobs/job1.settings")
    # generate the script content
    file_path, content = apps.generate_script_content(1, "test/job1_complete", "diann_2.0", settings, 16)
    # test the file path and the content
    assert file_path == "test/job1_complete/.cumulus.cmd"
    assert content == "cd 'test/job1_complete'\nSID=$(ps -p $$ --no-headers -o sid)\necho $SID > .cumulus.pid\nmkdir './output'\ntouch ./test/logs/job_1.stdout\nln -s ./test/logs/job_1.stdout .cumulus.stdout\ntouch ./test/logs/job_1.stderr\nln -s ./test/logs/job_1.stderr .cumulus.stderr\n/storage/share/diann-2.0/diann-linux --temp 'temp' --threads 15 --out './output/report.parquet' --f './test/data/AT2377PAP.mzML' --f './test/data/AT2378PAP.mzML' --f './test/data/AT2379PAP.mzML' --f './test/data/AT2381PAP.mzML' --f './test/data/AT2382PAP.mzML' --lib '' --fasta-search --predictor --gen-spec-lib --fasta 'Human_pSP_CMO_20190213.fasta' --cut 'K*,R*' --missed-cleavages 1 --min-pep-len 7 --max-pep-len 30 --min-pr-charge 1 --max-pr-charge 4 --min-pr-mz 300 --max-pr-mz 1800 --min-fr-mz 200 --max-fr-mz 1800 --pg-level 1 --var-mods 5 --unimod4 --var-mod UniMod:35,15.994915,M --var-mod UniMod:1,42.010565,*n --mass-acc-ms1 5.0 --mass-acc 15.0 --window 10 --reanalyse --peptidoforms --smart-profiling --matrices --qvalue 1.0 --verbose 1 1>> ./test/logs/job_1.stdout 2>> ./test/logs/job_1.stderr\n"

def test_is_file_required_true():
    # get the settings of a job
    settings = get_settings("test/jobs/job1.settings")
    assert apps.is_file_required("test/job1_complete", "diann_2.0", settings, "./test/data/AT2378PAP.mzML") == True

def test_is_file_required_false():
    # get the settings of a job
    settings = get_settings("test/jobs/job1.settings")
    assert apps.is_file_required("test/job1_complete", "diann_2.0", settings, "./test/data/AT2378PAP.raw") == False

def test_is_in_required_files_true():
    # get the settings of a job
    settings = get_settings("test/jobs/job1.settings")
    assert apps.is_in_required_files("test/job1_complete", "diann_2.0", settings, "AT2378") == True

def test_is_in_required_files_false():
    # get the settings of a job
    settings = get_settings("test/jobs/job1.settings")
    assert apps.is_in_required_files("test/job1_complete", "diann_2.0", settings, "AT2394") == False

def test_get_log_file_content():
    assert len(apps.get_log_file_content(1, True).strip("\n").split("\n")) == 815
    assert len(apps.get_log_file_content(1, False).strip("\n").split("\n")) == 1

def test_get_stdout_content():
    assert len(apps.get_stdout_content(1).strip("\n").split("\n")) == 815

def test_get_stderr_content():
    assert len(apps.get_stderr_content(1).strip("\n").split("\n")) == 1
