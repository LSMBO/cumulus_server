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
    if key in dictionnary:
        return dictionnary[key]
    elif "__default__" in dictionnary:
        return dictionnary["__default__"]
    else:
        return ""

def check_input_files(settings, data_dir, job_dir):
  # check the raw files
  for file in settings["files"]:
    if not os.path.isfile(data_dir + "/" + os.path.basename(file)): return False
  # check the fasta file
  fasta = f"{job_dir}/{os.path.basename(settings['fasta'])}"
  if not os.path.isfile(fasta): return False
  # if all the expected files are present
  return True

#def checkParameters(data_dir, params):
#    errors = []
#    # check the input files
#    for file in params["files"]:
#        filename = os.path.basename(file)
#        if not os.path.isfile(data_dir + "/" + file): errors.append(f"Raw file '{file}' not found")
#    # check the fasta file
#    fasta = f"{data_dir}/{os.path.basename(params['fasta'])}"
#    if not os.path.isfile(fasta): errors.append(f"Fasta file '{fasta}' not found")
#    return errors
#    # check other parameters?

# generic command from the module
def get_command_line(params, data_dir, nb_cpu):
    # it was put there to avoid the generation of .quant files, because it's not clear if we can choose where they are generated
    # it seems that they are always created where the raw files are, and it may be a problem when the same file is used twice at the same time
    cmd = f"wine ~/dia-nn-1.8.2b27/DiaNN.exe --dir '{data_dir}' --no-quant-files"
    for filename in params["files"]:
        # make sure that filename is just a file name, not a relative path
        cmd += f" --f '{os.path.basename(filename)}'"
        # add user arguments
    cmd += f" --lib '' --fasta '{data_dir}/{params['fasta']}' --fasta-search --predictor"
    cmd += f" --cut {params['protease']} --missed-cleavages {params['mc']}"
    cmd += f" --var-mods {params['var-mods']}"
    if params["met-excision"]: cmd += " --met-excision"
    # TODO add modifications
    cmd += f" --min-pep-length {params['min-pep-length']}  --max-pep-length {params['max-pep-length']}"
    cmd += f" --min-pr-charge {params['min-pr-charge']}  --max-pr-charge {params['max-pr-charge']}"
    cmd += f" --min-pr-mz {params['min-pr-mz']}  --max-pr-mz {params['max-pr-mz']}"
    cmd += f" --min-fr-mz {params['min-fr-mz']}  --max-fr-mz {params['max-fr-mz']}"
    cmd += f" --gen-spec-lib --qvalue {params['fdr']} --threads {nb_cpu} --verbose {params['verbose']}"
    cmd += f" --mass-acc {params['mass-acc']} --mass-acc-ms1 {params['ms1-acc']} --window {params['window']} --reanalyse"
    if params["slice-pasef"]: cmd += " --tims-scan"
    cmd += get_value(inference, params['inference'])
    cmd += get_value(classifier, params['classifier'])
    cmd += get_value(quant, params['quant'])
    cmd += get_value(norm, params['norm'])
    cmd += " --smart-profiling"
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

