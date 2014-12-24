##Description:

A python script that runs in the background and syncs a local folder to google-drive like Dropbox. This is
still very much a work in progress.

##System Requirements:

* python 2.7
* mongoDB

##Usage:

* Set **CLIENT_ID** and **CLIENT_SECRET** for accessing your google-drive as environment variables (for instance
in ~/.zshenv or ~/.bashrc

* The program takes one argument, namely the time interval between two successive syncs. To run script type:

```

$ ./drive.py [time]

```

where [time] is the number of seconds between syncs.

##Implemented so far:

* Uploading files, folders to different folder hierarchies
* Updating files in different folders
* Deleting files, folders in different hierarchies


##Todo:

* Moving a folder and all its contents to another target folder


