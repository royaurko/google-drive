##Description:

A python script that runs in the background and syncs a local folder to google-drive like Dropbox. This is
still very much a work in progress.

##System Requirements:

* python 2.7
* mongoDB

##Usage:

* Set **CLIENT_ID** and **CLIENT_SECRET** for accessing your google-drive as environment variables (for instance
in ~/.zshenv or ~/.bashrc

```

Usage: ./drive.py [Optional options...]

Optional Options:
  -t Time interval between syncs
  -f Folder to sync

```

By default the script monitors the folder where the script is located and the time interval between syncs is 10 seconds.

##Implemented so far:

* Uploading files, folders to different folder hierarchies
* Updating files in different folders
* Deleting files, folders in different hierarchies


##Todo:

* Moving a folder and all its contents to another target folder


