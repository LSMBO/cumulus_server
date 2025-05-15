# Cumulus Server

This repository is for the server for Cumulus.

Cumulus Server is a Flask REST API for Cumulus written in Python. It relies on Flask and Waitress to provide a REST API, that the clients can interrogate.

## Apps

Cumulus can run different apps, and every information about an app is on the server side exclusively. Every app is represented by a single XML file contained in the "apps" subdirectory.

The XML files will contain information about the app, its name, version, a description, and the command line to execute the app. It also contains all the parameters, with their type, their value, a tooltip text, etc. The XSD file to check the validity of the XML app is on the [Client side](https://github.com/LSMBO/cumulus-client/blob/main/server/apps.xsd).

Apps currently available are:
* [Dia-NN](https://github.com/vdemichev/DiaNN/) v2.0.2
* [AlphaDIA](https://github.com/MannLabs/alphadia) v1.10.1
* [Sage](https://github.com/lazear/sage) v0.15.0-beta1

To add a new app, or a new version of an app, you need to write the corresponding XML file, put it in the "apps" subdirectory, and make sure the executable is working on each VM of the Cloud.

There are also some tools to convert input files to mzML ([ThermoRawFileParser](https://github.com/compomics/ThermoRawFileParser) v1.4.5 and [tdf2mzml](https://github.com/mafreitas/tdf2mzml) v0.4). In the XML file, you just have to indicate the the files have to be converted to mzML and the appropriate conversion will be added automatically.

## Jobs

Jobs are stored in a SQLite database. The database is very simple and will be recreated if it's erased. The database only contains the list of jobs, some information about them (owner, app name, settings, dates, directory, etc.). Output files and log files are stored on a shared storage unit.

## Hosts

The virtual machines that can be used by Cumulus are listed in the file "hosts.tsv". A default version of the file is [available here](cumulus.conf.default). This file contains one line per VM, with a name that will be displayed, an IP address, information to connect to this VM, and information about the ressources this VM offers.

A [script](add_new_host.py) has been written to facilitate the addition of a new VM. It takes several arguments (the information necessary to connect to the machine), and should connect to the machine, run the ["add_new_host.sh" script](add_new_host.sh) there, and gather some information that will be automatically added to the "hosts.tsv" file.

**_NOTE_** that this script may not work if the machine is not already in the known_hosts file. You may have to connect manually first to make sure the connection will work.

If you add new apps that require specific packages to work, you will have to update the "add_new_host.sh" script to make sure the packages will be installed. If you choose to install the packages manually on each VM, make sure that all VM have the packages installed.

## Start the server

Once the server is set up, hosts are added and apps are working, you can simply start the server with the following commands:
```
source .venv/bin/activate
python cumulus.py
```

Or if you prefer to have a service running, you have to create a start script that would look like this:
```
#!/bin/bash
source .venv/bin/activate
python cumulus.py
```

And then, if you are using systemd, create a Cumulus.service file in /etc/systemd/system/ with this content (adapt it to your own context):
```
[Unit]
Description=Cumulus Server Daemon

[Service]
User=ubuntu
Group=ubuntu
ExecStart=/usr/local/cumulus_server/start.sh

[Install]
WantedBy=multi-user.target
```

Finally, you can reload the service list, start and activate the service:
```
sudo systemctl daemon-reload
systemctl start Cumulus
systemctl enable Cumulus
```

## What is Cumulus

Cumulus is a three-part tool whose purpose is to run software on a Cloud, without requiring the users to have any computational knowledge. Cumulus is made of three elements: 
* [A client](https://github.com/LSMBO/cumulus-client) with a graphical user interface developped in Javascript using ElectronJS.
* [A server application](https://github.com/LSMBO/cumulus_server), running on the Cloud. The server will dispatch the jobs, monitor them, and store everything in a database. The server is developped in Python and provides a Flast REST API for the client and the agent.
* [A separate agent](https://github.com/LSMBO/cumulus_rsync) who manages the transfer of the files from client to server. The agent is developped in Python and provides a Flask REST API for the client.

Cumulus has been developped to work around the [SCIGNE Cloud at IPHC](https://scigne.fr/), it may require some modifications to work on other Clouds, depending on how the virtual machines are organized. The virtual machines currently in use for Cumulus are set up like this:
* A controller with 4 VCPU, 8GB RAM, 40GB drive, this is where cumulus-server is running. This VM is the only one with a public IP address.
* Four virtual machines with 16 to 64VCPU and 64 to 256GB RAM, this is where the jobs will be running. These VM can be accessed by the controller using SSH.
* A 15TB storage unit, mounted as a NFS shared drive on every VM so the content is shared with the same path. This is where the data, the jobs and apps will be stored.

The virtual machines on the Cloud are all running with Ubuntu 24.04, Cumulus has only been tested there so it's possible that some scripts may not work on a different Linux distribution.

The Agent's purpose is to provide a single queue to ease the transfer of large files. Cumulus has been developped to run applications dealing with mass spectrometry data, which are often between 1 and 10GB. Cumulus has been developped for a use in a work environment with a dedicated network, where data are stored on a server, and users are running apps on their own sessions. In that context, it is more effective to transfer data from the server directly, rather than from each user's session. The queue is stored in a local database, so it does not disappear if the agent has to be restarted.

The agent has been tested on a Windows server, and uses [cwRsync](https://www.itefix.net/cwrsync), but it should work on a Linux server using a local RSync command. Scripts to create a Windows service are provided.

