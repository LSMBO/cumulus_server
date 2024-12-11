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

import os
import re

CONFIG = {}

def load():
	# get the list of hosts from the file
	f = open("cumulus.conf", "r")
	for line in f.read().strip("\n").split("\n"):
		# do not consider comments (anything after // or #)
		line = re.sub(r"\s*\t*#.*", "", line.replace("//", "#"))
		# if the line still contains a key and a value
		if "=" in line:
			key, value = line.split("=")
			# trim everything on both sides
			CONFIG[key.strip()] = value.strip()
	f.close()

def get(key): 
	if len(CONFIG) == 0: load()
	return CONFIG[key]

def export():
	return {
		"output.folder": CONFIG["output.folder"],
		"data.max.age.in.days": CONFIG["data.max.age.in.days"],
		"controller.version": CONFIG["version"],
		"client.min.version": CONFIG["client.min.version"]
	}

def get_log_dir():
	log_dir = get("storage.logs.subpath")
	if not os.path.isfile(log_dir): os.mkdir(log_dir)
	return log_dir