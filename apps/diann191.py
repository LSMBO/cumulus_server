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

import logging
import os

logger = logging.getLogger(__name__)

# declare some dictionnaries
inference = {
	"isoforms": " --pg-level 0",
	"protein": " --pg-level 1",
	"genes": " --pg-level 2",
	"species": " --species-genes",
	"off": " --no-prot-inf",
	"__default__": " --pg-level 1"
}

classifier = {
	"single": "",
	"double": " --double-search",
	"off": " --no-nn",
	"__default__": ""
}

quant = {
	"ums/prec": "",
	"ums/acc": " --high-acc",
	"legacy": " --direct-quant",
	"__default__": ""
}

norm = {
	"global": " --global-norm",
	"rt": "",
	"signal": " --sig-norm",
	"off": " --no-norm",
	"__default__": ""
}

speed = {
	"optimal": "",
	"low ram": " --min-corr 1.0 --corr-diff 1.0 --time-corr-only",
	"high speed": " --min-corr 2.0 --corr-diff 1.0 --time-corr-only",
	"ultra fast": " --min-corr 2.0 --corr-diff 1.0 --time-corr-only --extracted-ms1",
	"__default__": ""
}

# secure way to get values
def get_value(dictionnary, key):
	if key in dictionnary: return dictionnary[key]
	elif "__default__" in dictionnary: return dictionnary["__default__"]
	else: return ""

def check_input_files(settings, job_dir, data_dir):
	# check the raw files
	for file in settings["files"]:
		file_path = data_dir + "/" + os.path.basename(file)
		if not os.path.isfile(file_path) and not os.path.isdir(file_path):
			logger.debug(f"Expected input file '{file_path}' is missing")
			return False
	# check the fasta file
	#fasta = f"{data_dir}/{os.path.basename(settings['fasta'])}"
	#fasta = os.path.basename(settings['fasta'])
	fasta = f"{job_dir}/{os.path.basename(settings['fasta'])}"
	if not os.path.isfile(fasta):
		logger.debug(f"Expected fasta file '{fasta}' is missing")
		return False
	# if all the expected files are present
	return True

# generic command from the module
def get_command_line(params, data_dir, nb_cpu):
	# it was put there to avoid the generation of .quant files, because it's not clear if we can choose where they are generated
	# it seems that they are always created where the raw files are, and it may be a problem when the same file is used twice at the same time
	exe = "/storage/share/diann-1.9.1/diann-linux"
	# cmd = f"{exe} --dir '{data_dir}' --temp . --no-quant-files"
	cmd = f"{exe} --temp '.' --no-quant-files --out './report.tsv'"
	for filename in params["files"]:
		# make sure that filename is just a file name, not a relative path
		# cmd += f" --f '{os.path.basename(filename)}'"
		cmd += f" --f '{data_dir}/{os.path.basename(filename)}'"
	# add user arguments
	# for the fasta, use the job dir which should be the current working directory
	#fasta = f"{data_dir}/{os.path.basename(params['fasta'])}"
	fasta = os.path.basename(params['fasta'])
	cmd += f" --lib '' --fasta '{fasta}' --fasta-search --predictor"
	cmd += f" --cut {params['protease']} --missed-cleavages {params['mc']}"
	cmd += f" --var-mods {params['var-mods']}"
	if "met-excision" in params: cmd += " --met-excision"
	if "carba" in params: cmd += " --unimod4"
	if "ox-m" in params: cmd += " --var-mod UniMod:35,15.994915,M"
	if "ac-nterm" in params: cmd += " --var-mod UniMod:1,42.010565,*n --monitor-mod UniMod:1"
	if "phospho" in params: cmd += " --var-mod UniMod:21,79.966331,STY --monitor-mod UniMod:21"
	if "k-gg" in params: cmd += " --var-mod UniMod:121,114.042927,K --monitor-mod UniMod:121 --no-cut-after-mod UniMod:121"
	cmd += f" --min-pep-length {params['min-pep-length']}  --max-pep-length {params['max-pep-length']}"
	cmd += f" --min-pr-charge {params['min-pr-charge']}  --max-pr-charge {params['max-pr-charge']}"
	cmd += f" --min-pr-mz {params['min-pr-mz']}  --max-pr-mz {params['max-pr-mz']}"
	cmd += f" --min-fr-mz {params['min-fr-mz']}  --max-fr-mz {params['max-fr-mz']}"
	cmd += f" --gen-spec-lib --qvalue {params['fdr']} --threads {nb_cpu} --verbose {params['verbose']}"
	cmd += f" --mass-acc {params['mass-acc']} --mass-acc-ms1 {params['ms1-acc']} --window {params['window']} --reanalyse"
	if "slice-pasef" in params: cmd += " --tims-scan"
	cmd += get_value(inference, params['inference'])
	cmd += get_value(classifier, params['classifier'])
	cmd += get_value(quant, params['quant'])
	cmd += get_value(norm, params['norm'])
	cmd += " --smart-profiling --xic"
	cmd += get_value(speed, params['speed'])

	return cmd

def is_finished(stdout):
	return stdout.endswith("Finished\n\n")

def is_file_required(settings, file):
	file = os.path.basename(file)
	for raw in settings["files"]:
		if os.path.basename(raw) == file: return True
	if os.path.basename(settings['fasta']) == file: return True
	return False

def search_file(settings, file_tag):
	for raw in settings["files"]:
		if file_tag in raw: return True
	if file_tag in settings['fasta']: return True
	return False
