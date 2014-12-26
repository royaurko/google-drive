#!/usr/bin/python
import os
import httplib2
import mimetypes
import time
import sys
from pymongo import MongoClient
from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from apiclient import errors
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
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



def mirror(path, drive_service, json_info):
    # Mirror remote content into the folder pointed by path
    cursor = json_info.find()
    # first download all the directories
    for entry in cursor:
        if entry['parents']:
            if entry['mimeType'] == 'application/vnd.google-apps.folder':
                # This means it is a directory
                if entry['parents'][0]['isRoot']:
                    # These folders are in the root directory
                    dir_path = path + '/' + entry['title']
                    mongo_id = entry['_id']
                    json_info = download_dir(dir_path, drive_service, json_info, mongo_id)
                else:
                    # These are subdirectories
                    current_id = entry['id']
                    dir_path = ''
                    flag = True
                    while not flag:
                        current_entry = json_info.find_one({'id': current_id})
                        print current_entry
                        if current_entry['parents']:
                            # Update flag to that of its parent
                            dir_path = current_entry['title'] + '/' + dir_path
                            current_id = current_entry['parents'][0]['id']
                            flag = current_entry['parents'][0]['isRoot']
                        else:
                            # Broken link
                            break
                    dir_path = path + '/' + dir_path
                    mongo_id = entry['_id']
                    json_info = download_dir(dir_path, drive_service, json_info, mongo_id)
    # Download files to appropriate folders
    cursor = json_info.find()
    for entry in cursor:
        print 'Looking at: ' + entry['title']
        if entry['parents']:
            # Do not download objects without parent attribute
            if entry['mimeType'] != 'application/vnd.google-apps.folder':
                # If it is not a folder
                if entry['parents'][0]['isRoot']:
                    # If it is in the root
                    parent_id = entry['parents'][0]['id']
                    json_info = download_file(path, drive_service, json_info, entry['id'], parent_id=parent_id)
                else:
                    # Figure out its parent, see if it is downloaded already
                    parent_id = entry['parents'][0]['id']
                    parent_info = json_info.find_one({'id': parent_id})
                    if parent_info is not None:
                        print parent_info
                        if 'path' in parent_info:
                            if parent_info['path'] is not None:
                                # This means the parent has already been downloaded
                                print parent_info['path']
                                mongo_id = entry['_id']
                                json_info = download_file(parent_info['path'], drive_service, json_info, entry['id'])
    return json_info

def download_dir(path, drive_service, json_info, mongo_id):
    json_info.update({'_id': mongo_id}, {"$set": {'path': path}})
    if not os.path.exists(path):
        print 'Making directory: ' + path
        os.makedirs(path)
    return json_info


def download_file(path, drive_service, json_info, file_id, parent_id=None):
    try:
        file = drive_service.files().get(fileId=file_id).execute()
    except errors.HttpError, error:
        print 'An error occured: %s' % error
    download_url = file.get('downloadUrl')
    # In case the directory structure doesn't exist
    print path
    if not os.path.exists(path):
        if parent_id is not None:
            mongo_id = json_info.find_one({'id': parent_id})['_id']
            download_dir(path, drive_service, json_info, mongo_id)
    title = path + '/' + file.get('title')
    if download_url:
        resp, content = drive_service._http.request(download_url)
        if resp.status == 200:
            # need to set path properly
            print 'Downloading: ' + title
            f = open(title, 'w')
            f.write(content)
            f.close()
            json_info.update({'id': file_id}, {"$set": {'path': path}})
            return json_info
        else:
            print 'An error occurred: %s' % resp
            return json_info
    else:
        # The file doesn't have any content stored on drive
        return json_info


def upload(file_name, drive_service, json_info, flag=True, parent_id=None):
    # Upload a file
    if flag:
        k = file_name.rfind('/') + 1
        fname = file_name[k:]
        mime_type = mimetypes.guess_type(file_name)
        if mime_type == (None, None):
            mime_type = 'text/plain'
        media_body = MediaFileUpload(file_name,
                                     mimetype=mime_type, resumable=True)
    else:
        # It is a folder, set appropriate mime type
        fname = file_name
        media_body = None
        mime_type = 'application/vnd.google-apps.folder'
    body = {
        'title': fname,
        'mimeType': mime_type
    }
    if parent_id:
        body['parents'] = [{'id': parent_id}]
    # Upload the returned metadata to mongodb
    try:
        file = drive_service.files().insert(body=body,
                                            media_body=media_body).execute()
        '''
        temp_dict = dict((k, file[k])
                         for
                         k
                         in
                         ('id', 'title', 'createdDate', 'modifiedDate'))
        json_id = json_info.insert(temp_dict)
        '''
    except errors.HttpError, error:
        print 'An error occured: %s' % error


def update(file_name, drive_service, json_info, parent_id=None):
    # Update existing file
    try:
        k = file_name.rfind('/') + 1
        fname = file_name[k:]
        cursor = json_info.find({'title': fname})
        file_id = ''
        for entries in cursor:
            if 'parents' in entries:
                if parent_id == entries['parents'][0]['id']:
                    file_id = entries['id']
                    print 'here'
            else:
                if parent_id is None:
                    file_id = entries['id']
        file = drive_service.files().get(fileId=file_id).execute()
        mime_type = mimetypes.guess_type(file_name)
        if mime_type == (None, None):
            mime_type = 'text/plain'
        media_body = MediaFileUpload(file_name,
                                     mimetype=mime_type, resumable=True)
        body = {
            'title': file_name,
            'description': '',
            'mimeType': mime_type
        }
        # Send file
        updated_file = drive_service.files().update(fileId=file_id, body=file,
                                                    media_body=media_body).execute()
    except errors.HttpError, error:
        print 'An error has occured: %s' % error


def delete(file_name, drive_service, json_info, parent_id=None):
    cursor = json_info.find({'title': file_name})
    for entries in cursor:
        # delete all files with the file name
        file_id = entries['id']
        if 'parents' in entries:
            if entries['parents'][0]['id'] == parent_id:
                json_info.remove({'title': file_name})
                try:
                    drive_service.files().delete(fileId=file_id).execute()
                except errors.HttpError, error:
                    print 'An error occurred: %s' % error
        else:
            json_info.remove({'title': file_name})
            try:
                drive_service.files().delete(fileId=file_id).execute()
            except errors.HttpError, error:
                print 'An error occured: %s' % error


def watch(path, interval, drive_service, json_info, log_file):
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
                    upload(os.path.join(root, f), drive_service, json_info, flag=True, parent_id=parent_id)
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Uploaded (new) file: ' + os.path.join(root, f) + '\n'
                    log_file.write(write_str)
            if modified_file:
                k = root.rfind('/') + 1
                title = root[k:]
                parent_info = json_info.find_one({'title': title})
                if parent_info is None:
                    parent_id = None
                else:
                    parent_id = parent_info['id']
                for f in modified_file:
                    update(os.path.join(root, f), drive_service, json_info, parent_id=parent_id)
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Uploaded (modified) file: ' + os.path.join(root, f) + '\n'
                    log_file.write(write_str)
            if removed_file:
                k = root.rfind('/') + 1
                title = root[k:]
                cursor = json_info.find_one({'title': title})
                if parent_info is None:
                    parent_id = None
                else:
                    parent_id = None
                for f in removed_file:
                    delete(f, drive_service, json_info, parent_id=parent_id)
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Removed file: ' + os.path.join(root, f) + '\n'
                    log_file.write(write_str)
            if added_dir:
                k = root.rfind('/') + 1
                title = root[k:]
                parent_info = json_info.find_one({'title': title})
                if parent_info is None:
                    parent_id = None
                else:
                    parent_id = parent_info['id']
                for f in added_dir:
                    upload(f, drive_service, json_info, flag=False, parent_id=parent_id)
                    before_dir[os.path.join(root, f)] = {}
                    before_file[os.path.join(root, f)] = {}
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Uploaded (new) directory: ' + os.path.join(root, f) + '\n'
                    log_file.write(write_str)
            if removed_dir:
                for f in removed_dir:
                    delete(f, drive_service, json_info)
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Removed directory: ' + os.path.join(root, f) + '\n'
                    log_file.write(write_str)
            before_file[root] = after_file[root]
            before_dir[root] = after_dir[root]


def helpmenu():
    print '\nUsage: ./drive.py [Optional Options...]\n'
    print '\nOptional Options:\n'
    print '-t Time interval to sync\n'
    print '-f Folder to sync\n'


if __name__ == '__main__':
    flag = 0
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
        write_str += 'Time interval between syncs: ' + str(interval) + '\n'
        log_file.write(write_str)
        json_info = initialize_db(drive_service, log_file)
        mirror(path, drive_service, json_info)
        # watch(path, interval, drive_service, json_info, log_file)
