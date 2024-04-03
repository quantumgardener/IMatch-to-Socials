## Pre-requisites
# pip3 install Mastodon.py

import sys
import mastodon
from api.IMatchAPI import IMatchAPI, IMatchUtility
import pprint
import datetime
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO) # Don't want this debug level to cloud ours
pp = pprint.PrettyPrinter(width=120)

MB = 1048576
MAX_SIZE = 15 * MB  # As advised by @shlee@aus.social on 2024-04-02
DXO = "DXO Pure Raw"

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
category = 'Socials|pixelfed'
candiateImageIDs = im.getCategoryFiles(category)

# Get the attributes for each of the candidate files. Files with an existing 
# attribute record are assumed to be already uploaded.
postedImages = im.getAttributes("pixelfed", candiateImageIDs)

# Compare candiates to postedImages. Candidate images without attributes are 
# not yet posted i.e., missing from flickr. Once successfully posted, an 
# attibute record is create for these imsages and they won't be posted again.
postedImageIDs = iu.listIDs(postedImages)
missingImages = set(candiateImageIDs) - set(postedImageIDs)
logging.info(f"{len(candiateImageIDs)} candidate images. {len(postedImageIDs)} already posted. {len(missingImages)} to process and upload.")

if len(missingImages) == 0:
    logging.info("Exiting: No files could be found to process.")
    raise SystemExit

# -----------------------------------------------------------------------------
# Now begins the process of collating the information to be posted alongside 
# the image itself. This is the information we want from the version to be be 
# posted, and later the master. Certain camera and shooting information is not
# propogated through the versions, so we will need to walk back up the version
# > master tree to obtain it.
params = {
    "fields"          : "filename,id,name,size",
    "tagtitle"        : "title",
    "tagdescription"  : "description",
    "tagkeywords"     : "hierarchicalkeywords",
    "varaperture"     : "{File.MD.aperture}",
    "varfocallength"  : "{File.MD.focallength|value:formatted}",
    "varheadline"     : "{File.MD.headline}",
    "variso"          : "{File.MD.iso|value:formatted}",            # will come from master when queried
    "varlens"         : "{File.MD.lens}",                           # will come from master when queried
    "varmodel"        : "{File.MD.model}",                          # will come from master when queried
    "varshutterspeed" : "{File.MD.shutterspeed|value:formatted}"    # will come from master when queried
}

# Get info for the missing images. We need the information above
# and some category information as well. The category information is used to
# generate some additional keywords.  
imagesInfo = im.getFileInfo(missingImages, params)
categoriesInfo = im.getFileCategories(missingImages, params={
    'fields' : 'path'
})

# Build a dictionary of output files from the information we have so far. With this we can overlay
# information sourced from the master files. The assumption being made is version information has been
# propogated down from the master (apart from camera and shooting info - see comment below)
#
# imagesInfo is a list of items. We start by pulling out the fields and building a dictionary for
# easier manipulation and matching, based on the image id.
outputImages = {}
for info in imagesInfo:
    outputImages[info['id']] = {}
    image = outputImages[info['id']]
    image['filename'] = info['fileName'] # done this way to change case
    for field in [
            'title',
            'name', 
            'description',
            'headline',
            'aperture',
            'focallength',
            'iso',
            'lens',
            'model',
            'shutterspeed',
            'size']:
        try:
            image[field] = info[field]
        except KeyError:
            logging.info(f"{field} missing for image {info['id']} at {info['fileName']}.")

    # Process and filter keywords. Not every keyword is to be made public
    image['keywords'] = []
    for keyword in info['keywords']:
        splits = keyword.split("|")
        match splits[0]:
            case 'genre':
                # Genre is tagged with itself and with "photography appended"
                for genre in splits[1:]:
                    image['keywords'].append(genre)
                    if genre != 'astrophotography':
                        image['keywords'].append(genre+"photography")
            case 'Location':
                image['keywords'].append(splits[3]) # town
                image['keywords'].append(splits[4]) # location
            case 'nature':
                for nature in splits[1:]:
                    image['keywords'].append(nature) # Get the leaf

    # Categories are already in a dictonary by image id so it's easy to match and put into additional keywords
    # These are primariy image processing characteristics attached to the version being uploaded
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

    # Remove spaced to clean up the keywords as tagging doesn't like spaces
    image['keywords'] = list(map(lambda x: x.replace(" ",""), image['keywords']))

    # Check for files that may be too large and provide a cursory warning. I had some issues that I
    # suspect were caused by large file sizes during testing.
    if info['size'] > MAX_SIZE:
        logging.warning(f'{info['fileName']} may be too large to upload: {info['size']/MB:2.1f} MB')
    
# Get shooting infomration from master images and update. EXIF is not propogated so we can't
# rely on the original values retrieved even having values, let alone being accurate. Replace
# whatever was retrieved earlier
for id in outputImages.keys():
    masterid = im.getMaster(id)
    masterInfo = im.getFileInfo([masterid],params)
    for field in [
                'aperture',
                'focallength',
                'iso',
                'lens',
                'model',
                'shutterspeed']:
        try:
            outputImages[id][field] = masterInfo[0][field]
        except KeyError:
            logging.info(f"{field} missing for master image {masterid} at {masterInfo[0]['fileName']}.")

# Validate all the expected fields exist and have a value
for image in outputImages:
    for field in [
            'title',
            'description',
            'headline'
        ]:
        try:
            x = outputImages[image][field]
        except KeyError:
            logging.error(f'Missing {field} for "{outputImages[image]['name']}". Exiting.')
            raise SystemExit

        # Format the description
        aperture = 'f/{0:.3g}'.format(float(outputImages[image]['aperture']))
        outputImages[image]['status'] = f"""{outputImages[image]['title']} -- {outputImages[image]['description']}

ISO {outputImages[image]['iso']}{outputImages[image]['dxo']} | {outputImages[image]['shutterspeed']}s | {aperture} | {outputImages[image]['focallength']}
{outputImages[image]['model']} | {outputImages[image]['lens']}

#{" #".join(outputImages[image]['keywords'])}"""

# for image in outputImages.values():

#     # Format the description
#     print(image)

#     shootingInfo = ""
#     if image['iso'].strip() != '':
#         shootingInfo += f"ISO {image['iso']}{image['dxo']} | "
#     if image['shutterspeed'].strip() != '':
#         shootingInfo += f"{image['shutterspeed']} sec | "
#     if image['aperture'] != '':
#         shootingInfo += 'f/{0:.3g} | '.format(float(image['aperture']))
#     if image['focallength'].strip() != '':
#         shootingInfo += f"{image['focallength']}"

#     # May need some tidy up
#     if shootingInfo[-3:] == " | ":
#         shootingInfo = shootingInfo[:-3]

#     if shootingInfo == '':
#         shootingInfo = "Shooting info not available"
    
#     cameraInfo = ""
#     if image['model'].strip() != '':
#         cameraInfo += f"{image['model']} | "
#     if image['lens'].strip() != '':
#         cameraInfo += f"{image['lens']}"

#     # May need some tidy up
#     if cameraInfo[-3:] == " | ":
#         cameraInfo = cameraInfo[:-3]
    
#     image['status'] = f"""{image['title']} -- {image['description']}

# {shootingInfo}
# {cameraInfo}

# #{" #".join(image['keywords'])}"""

## All ready to upload now.

# -----------------------------------------------------------------------------
# Create a Mastodon instance. Get secrets from IMatch
# https://www.photools.com/help/imatch/index.html#var_basics.htm
pixelfed = mastodon.Mastodon(
    access_token = im.getAppVar("pixelfed_token"),
    api_base_url = im.getAppVar("pixelfed_url")
)

# Fetch my account details. Serves as a good check of connection details
# before bothering to upload images. If it fails here, uploads won't work.
try:
    logging.info("Verifying account credentials...")
    account = pixelfed.account_verify_credentials()
    logging.info(f"...verified. Connected to {account['url']}")
except mastodon.MastodonNetworkError as mne:
    logging.error(f"Unable to obtain account details. Check URL {pixelfed_url}")
    print (mne)
    raise SystemExit
except mastodon.MastodonAPIError:
    logging.error("Unable to access credentials. Check token.")
    raise SystemExit
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    raise SystemExit

# If there are previous posts, uncomment and run the following
# to get a list of items. Have to manually update IMatch.

# statuses = pixelfed.account_statuses(account['id'])
# pp.pprint(statuses)
# for status in statuses:
#     print(status['id'], status['url'], status['created_at'])
#     for media in status['media_attachments']:
#         print(media['id'])
# raise SystemExit

## Make the magic. Upload photos.
progressCounter = 1
progressEnd = len(outputImages)
visibility = im.getAppVar("pixelfed_visibility")
    # The visibility parameter is a string value and accepts any of: 
        # ‘direct’ - post will be visible only to mentioned users 
        # ‘private’ - post will be visible only to followers 
        # ‘unlisted’ - post will be public but not appear on the public timeline 
        # ‘public’ - post will be public

for image in outputImages:
    try:
        # Prepare the image for attaching to the status. In Mastodon, "posts/toots" are all status
        # Upload the media, then the status with the media attached. 
 
        logging.info(f'Uploading ({progressCounter}/{progressEnd}) "{outputImages[image]['title']}" from "{outputImages[image]['filename']}"')
        media = pixelfed.media_post(  
            media_file = outputImages[image]['filename'], 
            description= outputImages[image]['headline']
        )
        logging.info("SUCCESS. Image uploaded.")

        # Create a new status with the uploaded image
        logging.info("Posting status...")
               
        status = pixelfed.status_post(
            status     = outputImages[image]['status'], 
            media_ids  = media, 
            visibility = visibility
        )

        logging.info(f"...status successfully created at {status['url']}")

        # Update the image in IMatch by adding the attributes below.
        im.setAttributes("pixelfed", [image], data = {
            'posted' : status['created_at'].isoformat()[:10],
            'media_id' : media['id'],
            'status_id' : status['id'],
            'url' : status['url']
        })

        progressCounter += 1

    except KeyError:
        logging.error("Missed validating an image field somewhere.")
        raise SystemExit
    except mastodon.MastodonAPIError as mae:
        logging.error(f"An API error occurred: {mae}.")
        raise SystemExit
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        raise SystemExit
    
logging.info("DONE.")