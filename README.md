##Description:

A python script that runs in the background and syncs a local folder to Google Drive like Dropbox. This is
still very much a work in progress.

##System Requirements:

* python 2.7
* mongoDB

##Usage:

* Set **CLIENT_ID** and **CLIENT_SECRET** for accessing your Google Drive account as environment variables (for instance
in ~/.zshenv or ~/.bashrc)

```

Usage: ./drive.py [Optional options...] &

Optional Options:
  -t Time interval between syncs
  -f Folder to sync

```

* By default the script monitors the folder where the script is located and the time interval between syncs is 10 seconds.

* The script maintains a log file named *log* which is located in the same directory as the script.   

##Implemented so far:

* Uploading files, folders from local to remote (preserving hierarchy)
* Updating files changed in local to remote (preserving hierarchy)
* Deleting remote files, folders deleted locally


##Todo:

* Download files and folders added remotely to local folder
* Update, delete files locally when updated, deleted remotely

