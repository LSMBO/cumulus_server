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

# we only need to know the original job folder
JOB_FOLDER=$1

# make sure the job folder ends with a slash
JOB_FOLDER="$JOB_FOLDER/"

# the first step is to create an alive file to let the controller know that the job has started
touch $JOB_FOLDER/.cumulus.alive

# make sure the temp job dir exists
TEMP_JOB_DIR="$HOME/job"
mkdir $TEMP_JOB_DIR

# set a log file in the temp job dir
LOG_FILE=$TEMP_JOB_DIR/.cumulus.log

# copy the job folder to a local folder, do it in background in case it's a large folder
# we use "rsync -a" instead of "cp -r" because the TEMP_JOB_DIR already exist
echo "[SERVER] Preparing environment" > $LOG_FILE
rsync -a $JOB_FOLDER $TEMP_JOB_DIR &
COPY_JOB_PID=$!
while kill -0 $COPY_JOB_PID 2>/dev/null; do
    sleep 5
    touch $JOB_FOLDER/.cumulus.alive
done

# make sure the output folder exists
mkdir -p $TEMP_JOB_DIR/output
# make the output folder the current working directory (just in case the job creates files in the current working directory)
cd $TEMP_JOB_DIR/output

# execute the job in the background and record STDOUT and STDERR in the same file
echo "[SERVER] Execute the script" >> $LOG_FILE
chmod +x $TEMP_JOB_DIR/.cumulus.cmd
# we use stdbuf to make sure the two streams are buffered and we prepend STDERR with a tag so we can recognize it in the GUI
stdbuf -oL -eL $TEMP_JOB_DIR/.cumulus.cmd 2> >(stdbuf -oL sed 's/^/[STDERR] /') | awk '{ print; fflush() }' >> "$LOG_FILE" & PID=$!
# store the PID in a file
echo $PID > $JOB_FOLDER/.cumulus.pid

# while the pid is running, transfer the logs to the $JOB_FOLDER/ folder every 30 seconds
while kill -0 $PID 2>/dev/null; do
    sleep 15
    cp $LOG_FILE $JOB_FOLDER/.cumulus.log
    touch $JOB_FOLDER/.cumulus.alive
    # record the CPU and RAM usage, it can be used later to plot the usage of the job
    dt=$(date '+%Y-%m-%d %H:%M:%S %Z')
    #cpu=$(ps -p "$PID" -o %cpu=)
    # mem=$(ps -p "$PID" -o %mem=)
		cpu=$(top -bn1 | grep "Cpu(s)" | awk '{print 100 - $8}')
		mem=$(free | awk '/Mem/{printf "%.2f\n", $3/$2 * 100.0}')
    # echo "$dt	$cpu	$mem" >> $JOB_FOLDER/.cumulus.usage
    echo "[INFO] $dt;CPU:$cpu%;RAM:$mem%" >> $LOG_FILE
done
echo "[SERVER] End of the script" >> $LOG_FILE

# delete the PID file
rm $JOB_FOLDER/.cumulus.pid

# copy the content of job/output/ to the job folder, in background so we can keep the alive file updated while copying
echo "[SERVER] Transferring the output to the job directory" >> $LOG_FILE
rsync -a $TEMP_JOB_DIR/output $JOB_FOLDER/ &
COPY_PID=$!
# while the copy is running, update the alive file every 10 seconds
while kill -0 $COPY_PID 2>/dev/null; do
    sleep 15
    touch $JOB_FOLDER/.cumulus.alive
done
echo "[SERVER] All the files have been transferred" >> $LOG_FILE

# when the job finishes, transfer the finalized log file to the $JOB_FOLDER
cp $LOG_FILE $JOB_FOLDER/.cumulus.log

# rename the file $JOB_FOLDER/.cumulus.alive to .cumulus.stop to let the controller know that the job has finished
mv $JOB_FOLDER/.cumulus.alive $JOB_FOLDER/.cumulus.stop
