#!/usr/bin/python
import os
import httplib2
import time
import sys
from pymongo import MongoClient
from apiclient.discovery import build
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
from remote2local import mirror
from local2remote import upload, update, purge
# Set CLIENT_ID and CLIENT_SECRET as your environment variables

# Check https://developers.google.com/drive/scopes for all available scopes
OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive'

# Redirect URI for installed apps
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'


def initialize_db(drive_service, log_file):
    # Populate database with the current metadata
    client = MongoClient()
    db = client.drivedb
    json_info = db.drivedb
    file_list = drive_service.files().list().execute()['items']
    for i in range(len(file_list)):
        temp_dict = dict((k, file_list[i][k])
                         for
                         k
                         in
                         ('id', 'title', 'parents',
                         'mimeType', 'createdDate', 'modifiedDate'))
        temp_dict['path'] = None
        temp_dict['broken'] = False
        json_id = json_info.insert(temp_dict)
    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
    write_str += 'Database populated!\n'
    log_file.write(write_str)
    print 'Database initialized!'
    return json_info


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


def watch(path, interval, drive_service, json_info, log_file):
    print 'Monitoring local folder for changes...'
    forbidden = ['.git', '.credentials', 'log', 'drive.py', '.ropeproject']
    before_file = {}
    before_dir = {}
    after_dir = {}
    after_file = {}
    for root, dirs, files in os.walk(path, topdown=True):
        dirs[:] = [d for d in dirs if d not in forbidden]
        before_file[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f))))
                                  for f in files if f not in forbidden and '.swp' not in f])
        before_dir[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f))))
                                 for f in dirs if f not in forbidden and '.swp' not in f])
    while True:
        time.sleep(interval)
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
                    json_info = upload(os.path.join(root, f), drive_service, json_info, log_file, flag=True, parent_id=parent_id)
            if modified_file:
                k = root.rfind('/') + 1
                title = root[k:]
                for f in modified_file:
                    json_info = update(os.path.join(root, f), drive_service, json_info, log_file)
            if removed_file:
                k = root.rfind('/') + 1
                title = root[k:]
                for f in removed_file:
                    file_name = os.path.join(root, f)
                    json_info = purge(file_name, drive_service, json_info, log_file)
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
                    json_info = upload(file_name, drive_service, json_info, log_file, flag=False, parent_id=parent_id)
                    before_dir[file_name] = {}
                    before_file[file_name] = {}
            if removed_dir:
                for f in removed_dir:
                    file_name = os.path.join(root, f)
                    print file_name
                    json_info = purge(file_name, drive_service, json_info, log_file)
            before_file[root] = after_file[root]
            before_dir[root] = after_dir[root]


def helpmenu():
    print '\nUsage: ./drive.py [Optional Options...]\n'
    print '\nOptional Flag:\n'
    print '\nOptional Options:\n'
    print '-t Time interval to sync\n'
    print '-f Path to the local folder\n'


if __name__ == '__main__':
    flag = 0
    first_time = 'x'
    while (first_time != 'y') and (first_time != 'n'):
        first_time = raw_input('Is this the first time running this program? [y/n]: ')
    if len(sys.argv) == 1:
        path = os.getcwd()
        interval = 10
        flag = 1
    elif len(sys.argv) == 3:
        if sys.argv[1] == '-f':
            path = sys.argv[2]
            interval = 10
            flag = 1
        elif sys.argv[1] == '-t':
            interval = float(sys.argv[2])
            path = os.getcwd()
            flag = 1
        else:
            helpmenu()
    elif len(sys.argv) == 5:
        if sys.argv[1] == '-t' and sys.argv[3] == '-f':
            interval = float(sys.argv[2])
            path = sys.argv[4]
            flag = 1
        elif sys.argv[1] == '-f' and sys.argv[3] == '-t':
            interval = float(sys.argv[4])
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
        write_str += 'Time interval between syncs: ' + str(interval) + ' sec\n'
        log_file.write(write_str)
        json_info = initialize_db(drive_service, log_file)
        if first_time == 'y':
            print 'Attempting to download all files and folders from Drive to your local folder...\n'
            mirror(path, drive_service, json_info, log_file)
        watch(path, interval, drive_service, json_info, log_file)
