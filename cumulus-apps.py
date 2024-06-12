#import logging
import os
import cumulus_config as config
import cumulus_utils as utils
import apps.diann181 as diann181
import apps.diann182 as diann182
import apps.test_app as test

#logger = logging.getLogger(__name__)
FINAL_FILE = config.get("final.file")

def isFinished(appName, stdout):
  if appname == "diann_1.8.1": return diann181.isFinished(stdout)
  elif appname == "diann_1.8.2": return diann182.isFinished(stdout)
  elif appname == "test": return test.isFinished(stdout)
  else: return True

def areAllFilesTransfered(job_id, appName, settings):
  if os.path.isfile(f"{utils.JOB_DIR}/{job_id}/{FINAL_FILE}"):
    if appName == "diann_1.8.1": return diann181.checkInputFiles(settings, utils.DATA_DIR, utils.JOB_DIR)
    elif appName == "diann_1.8.2": return diann182.checkInputFiles(settings, utils.DATA_DIR, utils.JOB_DIR)
    elif appname == "test": return test.checkInputFiles(settings, utils.DATA_DIR, utils.JOB_DIR)
  return False

#def checkParameters(appName, settings):
#  if appName == "diann_1.8.1": return diann181.checkParameters(utils.DATA_DIR, settings)
#  elif appName == "diann_1.8.2": return diann182.checkParameters(utils.DATA_DIR, settings)
#  else: return []

def getCommandLine(appName, settings, host):
  # get the command line that corresponds to the application
  cmd = ""
  if appName == "diann_1.8.1": cmd = diann181.getCommandLine(settings, utils.DATA_DIR, host.cpu)
  elif appName == "diann_1.8.2": cmd = diann182.getCommandLine(settings, utils.DATA_DIR, host.cpu)
  elif appname == "test": cmd = test.getCommandLine(settings, utils.DATA_DIR, host.cpu)
  # default test command
  else: cmd = "sleep 60 &"

  # make sure the command ends with the log redirection and the ampersand
  if "1>" not in cmd: cmd += f" 1> {utils.getStdoutFileName(appName)}"
  if "2>" not in cmd: cmd += f" 2> {utils.getStderrFileName(appName)}"
  if not cmd.endswith(" &"): cmd += " &"
  return cmd

def is_file_required(appName, settings, file):
  if appName == "diann_1.8.1": return diann181.is_file_required(settings, file)
  elif appName == "diann_1.8.2": return diann182.is_file_required(settings, file)
  elif appname == "test": return test.is_file_required(settings, file)
  else: return False
