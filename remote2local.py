'''

This file contains all the functions that propagate changes from remote to local.

'''

import os
import shutil
import time
from apiclient import errors
from db import initialize_db
from pymongo import MongoClient
from local2remote import purge

def download_dir(drive_service, json_info, file_id, log_file):
    try:
        dir_path = json_info.find_one({'id': file_id})['path']
        if not os.path.exists(dir_path):
            write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
            write_str += 'Downloaded directory (local): ' + dir_path + '\n'
            log_file.write(write_str)
            os.makedirs(dir_path)
    except:
        print 'An error occurred downloading directory\n'


def download_file(drive_service, json_info, file_id, log_file, parent_id=None):
    try:
        file = drive_service.files().get(fileId=file_id).execute()
    except errors.HttpError, error:
        print 'An error occured: %s' % error
    download_url = file.get('downloadUrl')
    file_path = json_info.find_one({'id': file_id})['path']
    if download_url:
        resp, content = drive_service._http.request(download_url)
        if resp.status == 200:
            # Need to check time stamp
            if not os.path.isfile(file_path):
                f = open(file_path, 'w')
                f.write(content)
                f.close()
                write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                write_str += 'Downloaded file (local): ' + file_path + '\n'
                log_file.write(write_str)
            else:
                # File already exists, maybe it was modified in remote
                entry = json_info.find_one({'id': file_id})
                mtime_remote = entry['modifiedDate']
                # This is in RFC3399 need to convert it into UTC
                mtime_local = time.ctime(os.path.getmtime(file_path))
                # for now just download file, need to check modify time
                f = open(file_path, 'w')
                f.write(content)
                f.close()
                write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                write_str += 'Downloaded file (local): ' + file_path + '\n'
                log_file.write(write_str)
        else:
            print 'An error occurred: %s' % resp


def mirror_dir(drive_service, json_info, log_file):
    cursor = json_info.find({'mimeType':'application/vnd.google-apps.folder'})
    for entry in cursor:
        file_id = entry['id']
        if 'labels' in entry:
            if 'trashed' in entry['labels']:
                if entry['labels']['trashed']:
                    # If it is trashed don't download it
                    continue
        download_dir(drive_service, json_info, file_id, log_file)


def mirror_file(drive_service, json_info, log_file):
    cursor = json_info.find()
    for entry in cursor:
            if entry['mimeType'] != 'application/vnd.google-apps.folder':
                # If it is not a folder
                file_id = entry['id']
                if 'labels' in entry:
                    if 'trashed' in entry['labels']:
                        if entry['labels']['trashed']:
                            # If it is trashed don't download it
                            continue
                download_file(drive_service, json_info, file_id, log_file,)


def mirror(drive_service, json_info, log_file):
    # Mirror remote content into the folder pointed by path
    # first download all the directories
    mirror_dir(drive_service, json_info, log_file)
    # Download files to appropriate folders
    mirror_file(drive_service, json_info, log_file)
