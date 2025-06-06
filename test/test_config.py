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

def test_load():
	config.load("test/cumulus.conf")
	assert len(config.CONFIG) == 19

def test_get():
	assert config.get("database.file.path") == "./test/cumulus.db"

def test_init():
	config.init(False)
	assert config.DATA_DIR == "./test/data"

def test_export():
	assert config.export() == {
		"output.folder": "output",
		"temp.folder": "temp",
		"data.max.age.in.days": "90",
		"controller.version": "0.5.0",
		"client.min.version": "0.5.0"
	}

def test_get_final_stdout_path():
	assert config.get_final_stdout_path(1) == "./test/logs/job_1.stdout"

def test_get_final_stderr_path():
	assert config.get_final_stderr_path(1) == "./test/logs/job_1.stderr"
