#!/usr/bin/env python

# pip install tzdata
# -----------------------------------------------------------------------------
# Pull a lot of the bulk processing out of the main script for ease of
# understanding what's where.

import sys
from IMatchAPI import IMatchAPI, IMatchUtility
from flickrapi import FlickrAPI, FlickrError
import pprint
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('requests_oauthlib').setLevel(logging.INFO)
logging.getLogger('oauthlib').setLevel(logging.INFO)
logging.getLogger("flickrapi.core").setLevel(logging.WARN)
pp = pprint.PrettyPrinter(width=120)

FORCE_DETAILS = False            # Do we want to force missing details are present?
MB = 1048576
MAX_SIZE = 200 * MB
DXO = "DXO Pure Raw"
FLICKR_CACHE = "flickr-data.json"

def getIMatchInfo():
    # -----------------------------------------------------------------------------
    # Check version as code uses the match (case/switch) statement introduced in 
    # Python 3.10 for keyword processing
    if (sys.version_info.major < 3):
        logging.error(f"Python version 3.10 or later required. You are running with version {sys.version_info.major}.{sys.version_info.minor}")
        raise SystemExit
    elif (sys.version_info.major == 3) and (sys.version_info.minor < 10):
        logging.error(f"Python version 3.10 or later required. You are running with version {sys.version_info.major}.{sys.version_info.minor}")
        raise SystemExit

    # -----------------------------------------------------------------------------
    # Set up the connection to IMatch and utility helper class
    im = IMatchAPI()
    iu = IMatchUtility()

    # -----------------------------------------------------------------------------
    # Retrieve the complete set of images from IMatch. Determine which need to be 
    # uploaded
    category = "Socials|flickr"
    candiateImageIDs = im.getCategoryFiles(category)

    # Get the attributes for each of the candidate files. Files with an existing 
    # attribute record are assumed to be already uploaded.
    postedImages = im.getAttributes("flickr", candiateImageIDs)

    # Compare candiates to postedImages. Candidate images without attributes are 
    # not yet posted i.e., missing from flickr. Once successfully posted, an 
    # attibute record is create for these imsages and they won't be posted again.
    postedImageIDs = iu.listIDs(postedImages)
    missingImageIDs = set(candiateImageIDs) - set(postedImageIDs)
    logging.info(f"{len(candiateImageIDs)} candidate images. {len(postedImageIDs)} already posted. {len(missingImageIDs)} to process and upload.")

    if len(missingImageIDs) == 0:
        logging.info("Exiting: No files could be found to process.")
        raise SystemExit

    # -----------------------------------------------------------------------------
    # Now begins the process of collating the information to be posted alongside 
    # the image itself. The attributes on an image determine its upload state, BUT
    # I rely on the master to have all the metadata required. There are multiple
    # reasons for this.
    #   1. Certain camera and shooting information is not # propogated through 
    #      to the versions, so we will need to walk back up the version > master
    #      tree to obtain it anyway.
    #   2. We don't need to rely on propogation to have occurred.
    #   3. When something is missing, it's a PITA to find the version, go to the
    #      master, update it there and propogate.
    #   4. Sometimes, there is no editing required so uploading the master is fine

    params = {
        "fields"          : "filename,id,size",
    }

    # Grab the filename, the rest comes from the master
    imagesInfo = im.getFileInfo(candiateImageIDs, params)
    categoriesInfo = im.getFileCategories(candiateImageIDs, params={
        'fields' : 'path,description'
    })
    
    # Build a dictionary of output files from the information we have so far. With this we can overlay
    # information sourced from the master files. 
    #
    # imagesInfo is a list of items. We start by pulling out the fields and building a dictionary for
    # easier manipulation and matching, based on the image id.
    outputImages = {}
    for info in imagesInfo:
        outputImages[info['id']] = {
            'filename' : info['fileName'], # done this way to change case
            'size'     : info['size'],
            'keywords' : [],
            'albums'   : [],
            'groups'   : []
        }

        # Categories are already in a dictonary by image id so it's easy to match and put into additional keywords
        # These are primariy image processing characteristics attached to the version being uploaded
        image = outputImages[info['id']]
        image['dxo'] = ""
        for categories in categoriesInfo[info['id']]:
            splits = categories['path'].split("|")
            match splits[0]:
                case 'Image Characteristics':
                    split = splits.pop()
                    if split == DXO:
                        image['dxo'] = ' (DXO Pure Raw)' #capture this to tag the ISO value later on
                    else:
                        image['keywords'].append(split) # Get the leaf     
                case "Socials":
                    if splits[1] == "flickr":
                        # Need to grab any albums and groups
                        try:
                            if splits[2] == "albums":
                                # Code is in the name
                                category = splits[3].split("[")[1][:-1] # Pull the code from between the [ ]
                                image["albums"].append(category)
                            if splits[2] == "groups":
                                # Code is in the description due to the presence of @ being illegal in the name
                                image["groups"].append(categories['description'])
                        except IndexError:
                            pass #no groups or albums found

        # Check for files that may be too large and provide a cursory warning.
        if info['size'] > MAX_SIZE:
            logging.warning(f'{info['fileName']} may be too large to upload: {info['size']/MB:2.1f} MB')

    # Now get all information from the master, assuming no propogatation has ocurred
    # and to collect shooting information that would not have propogated anyway
            
    masterParams = {
        "fields"           : "filename,id",
        "tagtitle"         : "title",
        "tagdescription"   : "description",
        "taghierarchykeys" : "hierarchicalkeywords",
    }

    for id in outputImages.keys():
        masterID = im.getMaster(id)
        if masterID == None:
            # We are the master, use original id
            masterID = id
        info = im.getFileInfo([masterID],masterParams)[0]
        image = outputImages[id]

        # These are the fields we must have
        for field in [
            'title',
            'description',
            ]:
            try:
                image[field] = info[field]
            except KeyError:
                if FORCE_DETAILS:
                    logging.error(f"{field} missing for image {masterID} at {info['fileName']}")
                    raise SystemExit
                else:
                    logging.warning(f"{field} missing for image {masterID} at {info['fileName']}")
                    image[field] = ""
                    
        # Process and filter keywords. Not every keyword is to be made public
        try:
            for keyword in info['hierarchykeys']:
                splits = keyword.split("|")
                match splits[0]:
                    case 'genre':
                        # Genre is tagged with itself and with "photography appended"
                        for genre in splits[1:]:
                            image['keywords'].append(genre)
                            if genre != 'astrophotography':
                                image['keywords'].append(genre+"photography")
                    case 'Location':
                        try:
                            image['keywords'].append(splits[3]) # town
                            image['keywords'].append(splits[4]) # location
                        except IndexError:
                            pass
                        
                    case 'nature':
                        for nature in splits[1:]:
                            image['keywords'].append(nature) # Get the leaf
        except KeyError:
            logging.error(f"Keywords not found for image {masterID} at {info['fileName']}.")
            raise SystemExit
        

        # Remove spaced to clean up the keywords as tagging doesn't like spaces
        image['keywords'] = list(map(lambda x: x.replace(" ",""), image['keywords']))


    return {
        "api"        : im,
        "candidates" : candiateImageIDs,
        "posted"     : postedImageIDs,
        "missing"    : missingImageIDs,
        "data"       : outputImages
    }


def getFlickrInfo(api, refresh=False):

    if refresh:
        # Force full refresh from flickr
        flickrInfo = _downloadFlickrInfo(api)
    else:
        # Don't hassle flickr if we alread have the information locally
        try:
            with open(FLICKR_CACHE) as f:
                flickrInfo = json.load(f)
            logging.info("Flickr information successfully fetched from cache.")

        except FileNotFoundError:
            # Off to flickr
            logging.warning("Conducting full fetch of photo information from flickr required.")
            flickrInfo = _downloadFlickrInfo(api)

    saveFlickrInfo(flickrInfo)
    return {
        'data' : flickrInfo
    }

def saveFlickrInfo(info):
    with open(FLICKR_CACHE, "w") as f:
        json.dump(info,f, ensure_ascii=False, indent=4)

def _downloadFlickrInfo(api): 
    flickrInfo = {}
    page = 1

    while True:
        try:
            resp = api.photos.search(user_id="142019185@N05", page=page, format="parsed-json")
            
            logging.info(f"flickr: Fetched photo information ({page}/{resp['photos']['pages']})")
            for photo in resp['photos']['photo']:
                flickrInfo[photo['id']] = {
                    'title'  : photo['title'],
                    'albums' : [],
                    'groups' : [],
                }
            
            if page < resp['photos']['pages']:
                page += 1
            else:
                break
        except FlickrError as fe:
            print(fe)
            raise SystemExit

    progress = 1
    for photo_id in flickrInfo:
        try:
            logging.info(f'flickr: Fetched album, group and date information for "{flickrInfo[photo_id]['title']}" ({progress}/{len(flickrInfo)})')

            resp = api.photos.getAllContexts(photo_id = photo_id, format="parsed-json")

            
            if 'set' in resp:
                for set in resp['set']: # a.k.a. albums
                    flickrInfo[photo_id]['albums'].append(set['id'])

            if 'pool' in resp:
                for pool in resp['pool']: # a.k.a. groups
                    flickrInfo[photo_id]['groups'].append(pool['id'])

            resp = api.photos.getInfo(photo_id = photo_id, format = "parsed-json")

            posted = datetime.fromtimestamp(int(resp['photo']['dates']['posted'])).astimezone(ZoneInfo("Australia/Melbourne"))
            flickrInfo[photo_id]['posted'] = posted.strftime("%Y-%m-%d")

            progress += 1

        except FlickrError as fe:
            print(fe)
            raise SystemExit
        
    return flickrInfo
