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

# This script will be sent to the new host and will be executed there
# For this script to work, we assume three things:
# - the system is Debian-based (it was tested on Ubuntu 22.04)
# - the system is up-to-date, especially the kernel (otherwise, apt install may require user input)
# - the user uses a certificate without password for authentication, so using sudo works without password

# this script must be stored in /cumulus/temp/ and must probably be executed with sudo

# the input parameters should be the job folder (ie. /cumulus/temp/job_XX) and a way to identify the volume to mount (ie. /dev/vdb)
JOB_ID=$1
JOB_FOLDER=$2
# LOG_FOLDER=$3

# the first step is to create an alive file to let the controller know that the job has started
touch $JOB_FOLDER/.cumulus.alive

# create empty log files
# touch $JOB_FOLDER/.cumulus.stdout
# touch $JOB_FOLDER/.cumulus.stderr
touch $JOB_FOLDER/.cumulus.log

# copy the job folder to a local folder, do it in background in case it's a large folder
cp -r $JOB_FOLDER ~/job &
COPY_JOB_PID=$!
while kill -0 $COPY_JOB_PID 2>/dev/null; do
    sleep 5
    touch $JOB_FOLDER/.cumulus.alive
done

# make sure the output folder exists
mkdir -p ~/job/output
# make the output folder the current working directory (just in case the job creates files in the current working directory)
cd ~/job/output
# # prepare a usage file
# echo "Time	CPU%	RAM%" > $JOB_FOLDER/.cumulus.usage

# Create a named pipe for centralized logging
logpipe="merged_pipe"
mkfifo "$logpipe"
# Start a logger process that writes everything to merged.log
cat "$logpipe" >> ~/job/.cumulus.log &
logger_pid=$!

# Function to prefix each line with a tag (stdout or stderr)
prefix_lines() {
    local tag="$1"
    while IFS= read -r line; do
        echo "[$tag] $line"
    done
}

# execute the job in the background and make sure the stdout and stderr are recorded in the job folder
# source .cumulus.cmd > ~/job/.cumulus.stdout 2> ~/job/.cumulus.stderr &
# we use tee to capture the stdout and stderr, and also send it to the logpipe so it is recorded in the merged log file
# source .cumulus.cmd > >(tee ~/job/.cumulus.stdout > "$logpipe") 2> >(tee ~/job/.cumulus.stderr >&2 > "$logpipe") &
source .cumulus.cmd > >(prefix_lines STDOUT > "$logpipe") 2> >(prefix_lines STDERR > "$logpipe") &
# store the PID in a file
PID=$!
echo $PID > $JOB_FOLDER/.cumulus.pid

# while the pid is running, transfer the logs to the $JOB_FOLDER/ folder every 30 seconds
while kill -0 $PID 2>/dev/null; do
    sleep 30
    # cp ~/job/.cumulus.stdout $JOB_FOLDER/.cumulus.stdout
    # cp ~/job/.cumulus.stderr $JOB_FOLDER/.cumulus.stderr
    cp ~/job/.cumulus.log $JOB_FOLDER/.cumulus.log
    touch $JOB_FOLDER/.cumulus.alive
    # record the CPU and RAM usage, it can be used later to plot the usage of the job
    dt=$(date '+%Y-%m-%d %H:%M:%S %Z')
    cpu=$(ps -p "$PID" -o %cpu=)
    mem=$(ps -p "$PID" -o %mem=)
    # echo "$dt	$cpu	$mem" >> $JOB_FOLDER/.cumulus.usage
    echo "[INFO] $dt;CPU:$cpu%;RAM:$mem%" > $logpipe
done

# when the job finishes, transfer the finalized logs to the $JOB_FOLDER
# cp ~/job/.cumulus.stdout $JOB_FOLDER/.cumulus.stdout
# cp ~/job/.cumulus.stderr $JOB_FOLDER/.cumulus.stderr
cp ~/job/.cumulus.log $JOB_FOLDER/.cumulus.log
# also delete the PID file
rm $JOB_FOLDER/.cumulus.pid

# copy the content of job/output/ to the job folder, in background so we can keep the alive file updated while copying
# cp -r /cumulus/workspace/output/* $JOB_FOLDER/
cp -r ~/job/output $JOB_FOLDER/ &
COPY_PID=$!
# while the copy is running, update the alive file every 10 seconds
while kill -0 $COPY_PID 2>/dev/null; do
    sleep 15
    touch $JOB_FOLDER/.cumulus.alive
done

# Give logger a moment to flush and clean up
sleep 1
kill "$logger_pid" 2>/dev/null
rm "$logpipe"

# rename the file $JOB_FOLDER/.cumulus.alive to .cumulus.stop to let the controller know that the job has finished
mv $JOB_FOLDER/.cumulus.alive $JOB_FOLDER/.cumulus.stop
