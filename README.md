##Description:

* A simple python program that fetches your Google Drive content to a local folder, waits for
you to finish editing content locally and on exiting saves all changes back to Drive. 

##System Requirements:

* python 2.7
* [mongoDB] (http://www.mongodb.org/)

##Usage:

* Set **CLIENT_ID** and **CLIENT_SECRET** for accessing your Google Drive account as environment variables (for instance
in ~/.zshenv or ~/.bashrc)

```

Usage: ./drive.py [Optional options...] &

Optional Options:
  -f Path to local folder (default: current folder)

```

* The script will ask you whether you want to fetch content from Drive to the target folder. Note 
that this will over write any files in the target folder with conflicting names.

* The script will not download any folders, subfolders, files that are not owned by you. 

* The script will wait while you work locally and make changes to your Google Drive.

* When you are done, press Ctrl-C to halt the execution of the script. Before exiting the script
will save all changes made locally back to Drive.

* The script maintains a log file named *log* which is located in the same directory as the script.   
