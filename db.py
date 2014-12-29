'''

This file contains functions that are responsible for maintaining the database

'''

import time
from pymongo import MongoClient


def create_db(path, drive_service, log_file):
    # Populate database with the current metadata
    client = MongoClient()
    db = client.googledrivedb
    json_info = db.drivedb
    # Initialize a collection on this database from Drive
    initialize_db(path, drive_service, json_info)
    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
    write_str += 'Database updated!\n'
    log_file.write(write_str)
    return db


def initialize_db(path, drive_service, json_info):
    # Clear database just to be sure
    json_info.remove()
    cursor = json_info.find()
    file_list = drive_service.files().list().execute()['items']
    print len(file_list)
    for i in range(len(file_list)):
        temp_dict = dict((k, file_list[i][k])
                         for
                         k
                         in
                         ('id', 'title', 'parents',
                         'mimeType', 'createdDate', 'modifiedDate'))
        temp_dict['path'] = None
        # Check if a file with that id has already been inserted
        cursor = json_info.find({'id': temp_dict['id']})
        if cursor.count() == 0:
            # Hasn't been inserted in database yet
            json_id = json_info.insert(temp_dict)
        else:
            print 'Duplicate\n'
    remove_orphans(path, json_info)


def remove_orphans(path, json_info):
    # Removes entries with orphans and populates path for the rest
    cursor = json_info.find()
    for entry in cursor:
        if 'parents' in entry:
            if entry['parents']:
                # parents array is not empty, attempt to trace ancestor to root
                broken = False
                current_id = entry['id']
                current_entry = json_info.find_one({'id': current_id})
                if current_entry is None:
                    # broken
                    json_info.remove({'id': entry['id']})
                    continue
                orphans = set([])
                file_path = entry['title']
                while True:
                    if 'parents' in current_entry:
                        if current_entry['parents']:
                            # If it is root, not broken, exit
                            if current_entry['parents'][0]['isRoot']:
                                break
                            else:
                                orphans.add(current_id)
                                current_id = current_entry['parents'][0]['id']
                                current_entry = json_info.find_one({'id': current_id})
                                if current_entry is None:
                                    broken = True
                                    break
                                else:
                                    file_path = current_entry['title'] + '/' + file_path
                        else:
                            broken = True
                            break
                    else:
                        broken = True
                        break
                if broken:
                    # Remove  list of orphans from database
                    for f in orphans:
                        json_info.remove({'id': f})
                else:
                    # Set paths appropriately
                    file_path = path + '/' + file_path
                    json_info.update({'_id': entry['_id']}, {"$set": {'path': file_path}})
            else:
                # Parent data is empty array
                json_info.remove({'_id': entry['_id']})
        else:
            # there is no parents data
            json_info.remove({'_id': entry['_id']})
