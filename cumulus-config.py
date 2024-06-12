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
