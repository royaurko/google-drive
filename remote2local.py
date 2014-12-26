import os

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

