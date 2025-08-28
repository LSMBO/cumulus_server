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


# This script allows the administrator to create a new snapshot of the template server.
# The administrator can add new software or update dependencies on the template server, and then test it directly.
# Once the template server is ready, this script will create a new snapshot of it, that can be used to create temporary servers for the next jobs.
# The previous snapshot will be kept, the new one will be used by default. Any other snapshot will be deleted.

#!/bin/bash

VOLUME="cumulus-template-volume"
SNAPSHOT_NAME="cumulus-template-snapshot"

# create a new snapshot with a temporary name
# use --force because the volume cannot be detached from the server (it's the boot volume)
openstack volume snapshot create --volume "$VOLUME" --force "$SNAPSHOT_NAME-new"

# delete the previous snapshot if it exists
if openstack volume snapshot show "$SNAPSHOT_NAME-previous" >/dev/null 2>&1; then
    openstack volume snapshot delete "$SNAPSHOT_NAME-previous"
fi

# rename the current snapshot to previous if it exists
if openstack volume snapshot show "$SNAPSHOT_NAME" >/dev/null 2>&1; then
    openstack volume snapshot set --name "$SNAPSHOT_NAME-previous" "$SNAPSHOT_NAME"
fi

# rename the new snapshot to the current name
openstack volume snapshot set --name "$SNAPSHOT_NAME" "$SNAPSHOT_NAME-new"

echo "New snapshot $SNAPSHOT_NAME created successfully."
