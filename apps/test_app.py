def checkInputFiles(settings, data_dir, job_dir):
  # check the raw files
  for file in settings["files"]:
    if not os.path.isfile(data_dir + "/" + os.path.basename(file)): return False
  # check the fasta file
  fasta = f"{job_dir}/{os.path.basename(settings['fasta'])}"
  if not os.path.isfile(fasta): return False
  # if all the expected files are present
  return True

def getCommandLine():
  args = []
  for file in settings["files"]:
    args.append(data_dir + "/" + os.path.basename(file))
  args.append(f"{job_dir}/{os.path.basename(settings['fasta'])}")
  return "perl /storage/share/test.pl '" + "' '".join(args) + "'"

def isFinished(stdout):
  return stdout.endswith("All done!\n")

def is_file_required(settings, file):
  file = os.path.basename(file)
  for raw in settings["files"]:
    if os.path.basename(raw) == file: return True
  if os.path.basename(settings['fasta']) == file: return True
  return False
