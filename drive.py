#!/usr/bin/python
import os
import httplib2
import time
import sys
from apiclient.discovery import build
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
from remote2local import mirror
from local2remote import upload, update, purge
from db import create_db, initialize_db
# Set CLIENT_ID and CLIENT_SECRET as your environment variables

# Check https://developers.google.com/drive/scopes for all available scopes
OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive'

# Redirect URI for installed apps
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'


def authorize():
    # Check if credentials already exist
    fname = '.credentials'
    if os.path.isfile(fname):
        storage = Storage('.credentials')
        credentials = storage.get()
    else:
        # Create a flow object to get user authentication
        flow = OAuth2WebServerFlow(os.environ['CLIENT_ID'],
                                   os.environ['CLIENT_SECRET'],
                                   OAUTH_SCOPE, redirect_uri=REDIRECT_URI)
        authorize_url = flow.step1_get_authorize_url()
        print 'Go to the following link in your browser: ' + authorize_url
        code = raw_input('Enter verification code: ').strip()
        credentials = flow.step2_exchange(code)
        # Store credentials for future use
        storage = Storage('.credentials')
        storage.put(credentials)

    # Create an httplib2.Http object and authorize it with our credentials
    http = httplib2.Http()
    http = credentials.authorize(http)

    drive_service = build('drive', 'v2', http=http)
    return drive_service


def watch(path, drive_service, db, log_file):
    try:
        # Build the local directory structure
        json_info = db.drivedb
        forbidden = ['.git', '.credentials', 'log', 'drive.py', '.ropeproject']
        before_file = {}
        before_dir = {}
        # Populate the before_file and before_dir list
        for root, dirs, files in os.walk(path, topdown=True):
            dirs[:] = [d for d in dirs if d not in forbidden]
            before_file[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f))))
                                    for f in files if f not in forbidden and '.swp' not in f])
            before_dir[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f))))
                                    for f in dirs if f not in forbidden and '.swp' not in f])
        print 'Press [Ctrl]-C to exit and upload local changes to Drive '
        while True:
            pass
    except KeyboardInterrupt:
        after_dir = {}
        after_file = {}
        # Re create a list of the local files and folders
        for root, dirs, files in os.walk(path, topdown=True):
            dirs[:] = [d for d in dirs if d not in forbidden]
            after_file[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f))))
                                for f in files if f not in forbidden and '.swp' not in f])
            after_dir[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f))))
                                for f in dirs if f not in forbidden and '.swp' not in f])
            # Get list of files changed since last check
            added_file = [f for f in after_file[root] if f not in before_file[root]]
            removed_file = [f for f in before_file[root] if f not in after_file[root]]
            modified_file = [f
                             for
                             f
                             in
                             before_file[root] if f in after_file[root]
                             and
                             before_file[root][f] != after_file[root][f]]
            # Get list of directories changed since last check
            added_dir = [f for f in after_dir[root] if f not in before_dir[root]]
            removed_dir = [f for f in before_dir[root] if f not in after_dir[root]]
            if added_file:
                k = root.rfind('/') + 1
                title = root[k:]
                parent_info = json_info.find_one({'title': title})
                if parent_info is None:
                    parent_id = None
                else:
                    parent_id = parent_info['id']
                for f in added_file:
                    upload(os.path.join(root, f), drive_service, json_info, log_file, flag=True, parent_id=parent_id)
            if modified_file:
                k = root.rfind('/') + 1
                title = root[k:]
                for f in modified_file:
                    update(os.path.join(root, f), drive_service, json_info, log_file)
            if removed_file:
                k = root.rfind('/') + 1
                title = root[k:]
                for f in removed_file:
                    file_name = os.path.join(root, f)
                    purge(file_name, drive_service, json_info, log_file)
            if added_dir:
                k = root.rfind('/') + 1
                title = root[k:]
                parent_info = json_info.find_one({'title': title, 'path': root})
                if parent_info is None:
                    parent_id = None
                else:
                    parent_id = parent_info['id']
                for f in added_dir:
                    file_name = os.path.join(root, f)
                    upload(file_name, drive_service, json_info, log_file, flag=False, parent_id=parent_id)
                    before_dir[file_name] = {}
                    before_file[file_name] = {}
            if removed_dir:
                for f in removed_dir:
                    file_name = os.path.join(root, f)
                    purge(file_name, drive_service, json_info, log_file)
        print 'Changes saved, exiting...'
        db.drop_collection(db.drivedb)
        db.drop_collection(db.tmpdb)


def helpmenu():
    print '\nUsage: ./drive.py [Optional Options...]\n'
    print '\nOptional Options:\n'
    print '-f Path to the local folder (default: current folder)\n'


if __name__ == '__main__':
    flag = 0
    first_time = 'x'
    while (first_time != 'y') and (first_time != 'n'):
        first_time = raw_input('Fetch content from Drive to local folder? [y/n]: ')
    if len(sys.argv) == 1:
        path = os.getcwd()
        flag = 1
    elif len(sys.argv) == 3:
        if sys.argv[1] == '-f':
            path = sys.argv[2]
            flag = 1
        else:
            helpmenu()
    else:
        helpmenu()
    if flag > 0:
        drive_service = authorize()
        log_file = open('log', 'wb', 0)
        write_str = 'Monitoring folder: ' + path + '\n'
        log_file.write(write_str)
        db = create_db(path, drive_service, log_file)
        if first_time == 'y':
            print 'Downloading all files and folders from Drive to your local folder...'
            mirror(drive_service, db.drivedb, log_file)
        watch(path, drive_service, db, log_file)
