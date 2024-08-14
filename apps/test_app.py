import logging
import os

logger = logging.getLogger(__name__)

def check_input_files(settings, job_dir, data_dir):
	print(settings)
	# check the raw files
	for file in settings["files"]:
		file_path = data_dir + "/" + os.path.basename(file)
		if not os.path.exists(file_path):
			logger.debug(f"Expected input file '{file_path}' is missing")
			return False
	# check the fasta file
	fasta = f"{job_dir}/{os.path.basename(settings['fasta'])}"
	if not os.path.isfile(fasta):
		logger.debug(f"Expected fasta file '{fasta}' is missing")
		return False
	# if all the expected files are present
	return True

def get_command_line(settings, data_dir):
	args = []
	for file in settings["files"]:
		args.append(data_dir + "/" + os.path.basename(file))
	args.append(f"{data_dir}/{os.path.basename(settings['fasta'])}")
	return "perl /storage/share/test.pl '" + "' '".join(args) + "'"

def is_finished(stdout):
	return stdout.endswith("All done!\n")

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