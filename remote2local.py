'''

This file contains all the functions that propagate changes from remote to local.

'''

import os
import time
from apiclient import errors

def download_dir(path, drive_service, json_info, mongo_id, log_file):
    json_info.update({'_id': mongo_id}, {"$set": {'path': path}})
    if not os.path.exists(path):
        write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
        write_str += 'Downloaded directory: ' + path + '\n'
        log_file.write(write_str)
        os.makedirs(path)
    return json_info


def download_file(path, drive_service, json_info, file_id, log_file, parent_id=None):
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
            download_dir(path, drive_service, json_info, mongo_id, log_file)
    title = path + '/' + file.get('title')
    if download_url:
        resp, content = drive_service._http.request(download_url)
        if resp.status == 200:
            # need to set path properly
            if not os.path.isfile(title):
                f = open(title, 'w')
                f.write(content)
                f.close()
                write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                write_str += 'Downloaded file: ' + title + '\n'
                log_file.write(write_str)
                json_info.update({'id': file_id}, {"$set": {'path': path}})
        else:
            print 'An error occurred: %s' % resp
    return json_info


def mirror_dir(cursor, path, drive_service, json_info, log_file):
    for entry in cursor:
        if entry['parents']:
            # Only download folders that have well defined parents
            if entry['mimeType'] == 'application/vnd.google-apps.folder':
                # Only download folders
                if entry['parents'][0]['isRoot']:
                    # These folders are in the root directory
                    dir_path = path + '/' + entry['title']
                    mongo_id = entry['_id']
                    json_info = download_dir(dir_path, drive_service, json_info, mongo_id, log_file)
                else:
                    # These are subdirectories of directories inside the root
                    current_id = entry['id']
                    dir_path = ''
                    flag = False
                    broken = False
                    while not flag:
                        # Attempts to find the relative path by examining
                        # ancestors
                        current_entry = json_info.find_one({'id': current_id})
                        if current_entry is None:
                            json_info.update({'id': current_id}, {"$set": {'broken': True}})
                            broken = True
                            break
                        if 'parents' in current_entry:
                            if current_entry['parents']:
                                # Update flag to that of its parent
                                dir_path = current_entry['title'] + '/' + dir_path
                                current_id = current_entry['parents'][0]['id']
                                flag = current_entry['parents'][0]['isRoot']
                            else:
                                #Broken link
                                json_info.update({'id': current_id}, {"$set": {'broken': True}})
                                broken = True
                                break
                        else:
                            # Broken link
                            json_info.update({'id': current_id}, {"$set": {'broken': True}})
                            broken = True
                            break
                    if not broken:
                        dir_path = path + '/' + dir_path
                        mongo_id = entry['_id']
                        json_info = download_dir(dir_path, drive_service, json_info, mongo_id, log_file)
                    else:
                        json_info.update({'id': entry['id']}, {"$set": {'broken': True}})
                        write_str = 'Orphan directory: ' + entry['title'] + '\n'
                        log_file.write(write_str)
    tmp_cursor = json_info.find({'broken': True, 'mimeType': 'application/vnd.google-apps.folder'})


def mirror_file(cursor, path, drive_service, json_info, log_file):
    for entry in cursor:
        print 'Examining file: ' + entry['title']
        if entry['parents']:
            # Do not download objects without parent attribute
            if entry['mimeType'] != 'application/vnd.google-apps.folder':
                # If it is not a folder
                if entry['parents'][0]['isRoot']:
                    # If it is in the root
                    parent_id = entry['parents'][0]['id']
                    json_info = download_file(path, drive_service, json_info, entry['id'], log_file, parent_id=parent_id)
                else:
                    # Figure out its parent, see if it is downloaded already
                    parent_id = entry['parents'][0]['id']
                    parent_info = json_info.find_one({'id': parent_id})
                    if parent_info is not None:
                        # print parent_info
                        if 'path' in parent_info and 'broken' in parent_info:
                            if parent_info['path'] is not None and not parent_info['broken']:
                                # This means the parent has already been downloaded
                                mongo_id = entry['_id']
                                json_info = download_file(parent_info['path'], drive_service, json_info, log_file, entry['id'])
    return json_info


def mirror(path, drive_service, json_info, log_file):
    # Mirror remote content into the folder pointed by path
    cursor = json_info.find({'mimeType':'application/vnd.google-apps.folder'})
    # first download all the directories
    mirror_dir(cursor, path, drive_service, json_info, log_file)
    # Download files to appropriate folders
    cursor = json_info.find()
    mirror_file(cursor, path, drive_service, json_info, log_file)
    return json_info
