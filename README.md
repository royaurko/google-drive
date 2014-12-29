##Description:

* A bunch of python scripts to make Google Drive contents sync to a local folder. 

* When run for the first time the script attempts to download all files from Drive
 to the target folder (skipping over files already present), 
after which it keeps checking for changes in the local directory at regular intervals and mirrors it to Drive. 


* So far it correctly downloads all the content in the proper hierarchy and reflects local changes remotely. 

* Reflecting remote changes locally has not been correctly impelemented yet.

##System Requirements:

* python 2.7
* [mongoDB] (http://www.mongodb.org/)

##Usage:

* Set **CLIENT_ID** and **CLIENT_SECRET** for accessing your Google Drive account as environment variables (for instance
in ~/.zshenv or ~/.bashrc)

```

Usage: ./drive.py [Optional options...] &

Optional Options:
  -t Time interval between syncs
  -f Folder to sync

```

* The script will ask you whether this is the first time you are running it, in which case it will attempt to download
the files and folders from remote to your local target directory.

* The script will not download any folders, subfolders, files that are not owned by you.

* By default the script monitors the folder where the script is located and the time interval between syncs is 10 seconds.

* The script maintains a log file named *log* which is located in the same directory as the script.   

##Implemented so far:

* Uploading files, folders from local to remote (preserving hierarchy)
* Updating files changed in local to remote (preserving hierarchy)
* Deleting remote files, folders deleted locally


##Todo:

* Update/delete files locally when updated/deleted remotely

