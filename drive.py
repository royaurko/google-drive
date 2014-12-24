#!/usr/bin/python
import os
import httplib2
import pprint
import mimetypes
import time
import sys
import pymongo
import string
import re
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


def initialize_db(drive_service):
    # Populate database with the current metadata
    client = MongoClient()
    db = client.drivedb
    db.json_info.drop()
    json_info = db.drivedb
    file_list = drive_service.files().list().execute()['items']
    for i in range(len(file_list)):
        temp_dict = dict((k,file_list[i][k]) for k in ('id', 'title', 'parents', 'createdDate', 'modifiedDate'))
        json_id = json_info.insert(temp_dict)
    print 'Database populated!'
    return json_info


def authorize():
    # Check if credentials already exist
    fname = '.credentials'
    if os.path.isfile(fname):
        storage = Storage('.credentials')
        credentials = storage.get()
    else:
        # Create a flow object to get user authentication
        flow = OAuth2WebServerFlow(os.environ['CLIENT_ID'], os.environ['CLIENT_SECRET'], OAUTH_SCOPE,
                                                      redirect_uri=REDIRECT_URI)
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


def upload(file_name, drive_service, json_info, flag = True, parent_id = None):
    # Upload a file
    if flag:
        k = file_name.rfind('/') + 1
        fname = file_name[k:]
        mime_type = mimetypes.guess_type(file_name)
        if mime_type == (None, None):
            mime_type = 'text/plain'
        media_body = MediaFileUpload(file_name, mimetype = mime_type, resumable = True)
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
        file = drive_service.files().insert(body=body, media_body=media_body).execute()
        temp_dict = dict((k, file[k]) for k in ('id', 'title', 'createdDate', 'modifiedDate'))
        json_id = json_info.insert(temp_dict)
    except errors.HttpError, error:
        print 'An error occured: %s' % error

def update(file_name, drive_service, json_info, parent_id = None):
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
        file = drive_service.files().get(fileId = file_id).execute()
        mime_type = mimetypes.guess_type(file_name)
        if mime_type == (None, None):
            mime_type = 'text/plain'
        media_body = MediaFileUpload(file_name, mimetype = mime_type, resumable = True)
        body = {
            'title': file_name,
            'description': '',
            'mimeType': mime_type
        }
        # Send file
        updated_file = drive_service.files().update(fileId = file_id, body = file, media_body = media_body).execute()
    except errors.HttpError, error:
        print 'An error has occured: %s' % error


def delete(file_name, drive_service, json_info, parent_id = None):
    cursor = json_info.find({'title': file_name})
    for entries in cursor:
        # delete all files with the file name
        file_id = entries['id']
        if 'parents' in entries:
            if entries['parents'][0]['id'] == parent_id:
                json_info.remove({'title': file_name})
                try:
                    drive_service.files().delete(fileId = file_id).execute()
                except errors.HttpError, error:
                    print 'An error occurred: %s' % error
        else:
            json_info.remove({'title': file_name})
            try:
                drive_service.files().delete(fileId = file_id).execute()
            except errors.HttpError, error:
                print 'An error occured: %s' % error


def watch(path, interval, drive_service, json_info, log_file):
    forbidden = ['.git', '.credentials', 'log', 'drive.py', '.ropeproject']
    before_file = {}
    before_dir = {}
    after_dir = {}
    after_file = {}
    for root, dirs, files in os.walk(path, topdown = True):
        dirs[:] = [d for d in dirs if d not in forbidden]
        before_file[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f))))
                                  for f in files if f not in forbidden and not '.swp' in f])
        before_dir[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f))))
                                 for f in dirs if f not in forbidden and not '.swp' in f])
    while True:
        time.sleep(interval)
        # First check if any of the old files were modified
        for root, dirs, files in os.walk(path, topdown = True):
            dirs[:] = [d for d in dirs if d not in forbidden]
            after_file[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f))))
                                     for f in files if f not in forbidden and not '.swp' in f])
            after_dir[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f))))
                                    for f in dirs if f not in forbidden and not '.swp' in f])
            # Get list of files changed since last check
            added_file = [f for f in after_file[root] if not f in before_file[root]]
            removed_file = [f for f in before_file[root] if not f in after_file[root]]
            modified_file = [f for f in before_file[root] if f in after_file[root] and before_file[root][f]!=after_file[root][f]]
            # Get list of directories changed since last check
            added_dir = [f for f in after_dir[root] if not f in before_dir[root]]
            removed_dir = [f for f in before_dir[root] if not f in after_dir[root]]
            if added_file:
                k = root.rfind('/') + 1
                title = root[k:]
                parent_info = json_info.find_one({'title': title})
                if parent_info is None:
                    parent_id = None
                else:
                    parent_id = parent_info['id']
                for f in added_file:
                    upload(os.path.join(root, f), drive_service, json_info, flag = True, parent_id = parent_id)
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Uploaded (new) file: ' + os.path.join(root, f) + '\n'
                    log_file.write(write_str)
                print 'Added file', ','.join(added_file)
            if modified_file:
                k = root.rfind('/') + 1
                title = root[k:]
                parent_info = json_info.find_one({'title': title})
                if parent_info is None:
                    parent_id = None
                else:
                    parent_id = parent_info['id']
                for f in modified_file:
                    update(os.path.join(root, f), drive_service, json_info, parent_id = parent_id)
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Uploaded (modified) file: ' + os.path.join(root, f) + '\n'
                    log_file.write(write_str)
                print 'Modified file', ','.join(modified_file)
            if removed_file:
                k = root.rfind('/') + 1
                title = root[k:]
                cursor = json_info.find_one({'title': title})
                if parent_info is None:
                    parent_id = None
                else:
                    parent_id = None
                for f in removed_file:
                    delete(f, drive_service, json_info, parent_id = parent_id)
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
                    upload(f, drive_service, json_info, flag = False, parent_id = parent_id)
                    before_dir[os.path.join(root, f)] = {}
                    before_file[os.path.join(root, f)] ={}
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Uploaded (new) directory: ' + os.path.join(root, f) + '\n'
                    log_file.write(write_str)
                print 'Added directory: ', ','.join(added_dir)
            if removed_dir:
                for f in removed_dir:
                    delete(f, drive_service, json_info)
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Removed directory: ' + os.path.join(root, f) + '\n'
                    log_file.write(write_str)
                print 'Removed directory: ', ','.join(removed_dir)
            before_file[root] = after_file[root]
            before_dir[root] = after_dir[root]


if __name__ == '__main__':
    path = os.getcwd()
    interval = float(sys.argv[1])
    drive_service = authorize()
    json_info = initialize_db(drive_service)
    file_list = drive_service.files().list().execute()['items']
    log_file = open('log', 'wb', 0)
    watch(path, interval, drive_service, json_info, log_file)
