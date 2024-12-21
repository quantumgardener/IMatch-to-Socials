from datetime import datetime
import sys
import logging

import flickrapi

from imatch_image import IMatchImage
import IMatchAPI as im
from platform_base import PlatformController
import config

logging.getLogger("flickrapi.core").setLevel(logging.WARN)  # Hide basic info messages


class FlickrImage(IMatchImage):

    __MAX_SIZE = 200 * config.MB_SIZE

    def __init__(self, id, platform) -> None:
        super().__init__(id, platform)

        if self.size > FlickrImage.__MAX_SIZE:
            logging.warning(f'{self.name}: {self.filename} may be too large to upload: {self.size/config.MB_SIZE:2.1f} MB. Max is {FlickrImage.__MAX_SIZE/config.MB_SIZE:2.1f} MB.')

    def prepare_for_upload(self) -> None:
        """Build variables ready for uploading."""
        super().prepare_for_upload()

        #Set up the text items
        tmp_description = []

        if self.headline != "":
            tmp_description.append(self.headline)
            tmp_description.append('')

        tmp_description.append(self.description)
        tmp_description.append('')

        if self.circadatecreated != "":
            tmp_description.append(f"Taken ca. {self.date_time.strftime("%#d %B %Y")}.")
            tmp_description.append('')

        self.albums = []
        self.groups = []

        for category in self.categories:
            splits = category['path'].split("|")
            match splits[0]:
                case "Socials":
                    if splits[1] == "flickr":
                        # Need to grab any albums and groups
                        try:
                            if splits[2] == "albums":
                                # Code is in the description
                                self.albums.append(category['description'])
                            if splits[2] == "groups":
                                # Code is in the description due to the presence of @ being illegal in the name
                                self.groups.append(category['description'])
                        except IndexError:
                            pass #no groups or albums found

        shooting_info = self.shooting_info
        if shooting_info != '':
            tmp_description.append(shooting_info)
        
        camera_info = self.camera_info
        if camera_info != '':
            tmp_description.append(camera_info)

        self.full_description = "\n".join(tmp_description)       
        return None
    
    @property
    def is_valid(self) -> bool:
        result = super().is_valid
        for attribute in []:
            try:
                if getattr(self, attribute).strip() == '':
                    self.errors.append(f"missing {attribute}")
            except AttributeError:
                self.errors.append(f"missing {attribute}")
        if self.size > FlickrImage.__MAX_SIZE:
            logging.error(f'{self.controller.name}: Skipping {self.name} is too large to upload: {self.size/config.MB_SIZE:2.1f} MB. Max is {FlickrImage.__MAX_SIZE/config.MB_SIZE:2.1f} MB.')
            print(f'{self.controller.name}: Skipping {self.name} is too large to upload: {self.size/config.MB_SIZE:2.1f} MB. Max is {FlickrImage.__MAX_SIZE/config.MB_SIZE:2.1f} MB.')
            self.errors.append(f"file too large")
        return len(self.errors) == 0 and result

    @property
    def is_on_platform(self) -> bool:
        res = im.IMatchAPI.get_attributes("flickr", self.id)
        return len(res) != 0
    
class FlickrController(PlatformController):

    def __init__(self, platform) -> None:
        super().__init__(platform)
        self.privacy = {
            'is_public' : im.IMatchAPI.get_application_variable("flickr_is_public"),
            'is_family' : im.IMatchAPI.get_application_variable('flickr_is_family'),
            'is_friend' : im.IMatchAPI.get_application_variable('flickr_is_friend')
        }

        self.organisation_categories = {}
        for category in ['albums', 'groups']:
            category_info = im.IMatchAPI.get_category_info(
                category = im.IMatchUtility.build_category([
                    config.ROOT_CATEGORY,
                    self.name,
                    category
                    ]),
                params = {
                    'fields' : 'children,name,description'
                }
            )
            self.organisation_categories[category] = {}
            for imatch_cat in category_info[0]['children']:
                self.organisation_categories[category][imatch_cat['description']] = imatch_cat

    def connect(self):
        if self.api is not None:
            return
        else: 
            try:
                print(f"{self.name}: Work to do -- Connecting to platform.")
                flickr = flickrapi.FlickrAPI(
                    im.IMatchAPI.get_application_variable("flickr_apikey"),
                    im.IMatchAPI.get_application_variable("flickr_apisecret"),
                    cache=True
                    )
                flickr.authenticate_via_browser(
                    perms = 'delete'
                    )
                print(f"{self.name}: Authenticated.")
            except Exception as ex:
                logging.error(f"{self.name}: {ex}")
                sys.exit()
            
            self.api = flickr


    def commit_add(self, image):       
        """Make the api call to commit the image to the platform, and update IMatch with reference details"""
        try:
            response = self.api.upload(
                image.filename,
                title = image.title if image.title != '' else image.name,
                description = image.full_description,
                is_public = self.privacy['is_public'],
                is_friend = self.privacy['is_friend'],
                is_family = self.privacy['is_family'],
                )
            
            photo_id = response.findtext('photoid')
            
            # Since we expect no EXIF data in the file, flickr will take the upload time from the last modified date of the file
            # and ignore XMP::EXIF fields. Fix that by setting the time ourselves. The format we have is 
            response = self.api.photos.setDates(photo_id=photo_id, date_taken=str(image.date_time), date_taken_granularity=0)

            for album in image.albums:
                response = self.api.photosets_addPhoto(photoset_id=album, photo_id=photo_id)

            for group in image.groups:
                response = self.api.groups_pools_add(group_id=group, photo_id=photo_id)

            # flickr will bring in hierarchical keywords not under our control as level|level|level
            # which frankly is stupid. Easiest way is to delete them all. We don't know quite what
            # it will have loaded.
            ### THIS CODE IS NOT WORKING AND I CAN"T WORK OUT WHY. Does not delete, ALWAYS returns "ok"
            # resp = self.api.photos.getInfo(photo_id = photo_id, format = "parsed-json")
            # for badtag in resp['photo']['tags']['tag']:
            #     resp = self.api.photos.removeTag(tag=badtag['id'])
            #     
            
            # Now add back the "Approved" tags. If added on upload, they combine with IPTC weirdly
            resp = self.api.photos.addTags(tags=",".join(image.keywords), photo_id=photo_id)
        except flickrapi.FlickrError as fe:
                logging.error(fe)
                sys.exit(1)

        # Update the image in IMatch by adding the attributes below.
        posted = datetime.now().isoformat()[:10]
        im.IMatchAPI.set_attributes(self.name, image.id, data = {
            'posted' : posted,
            'photo_id' : photo_id,
            'url' : f"{im.IMatchAPI.get_application_variable("flickr_url")}/{photo_id}"
            })
                            
    def commit_delete(self, image):
        """Make the api call to delete the image from the platform"""
        try:
            attributes = im.IMatchAPI().get_attributes(self.name, image.id)[0]
            photo_id = attributes['photo_id']
            response = self.api.photos.delete(photo_id = photo_id)
        except flickrapi.FlickrError as fe:
            logging.error(fe)
            logging.error(response)
            sys.exit(1)

    def commit_update(self, image):
        """Make the api call to update the image on the platform"""
        try:
            attributes = im.IMatchAPI().get_attributes(self.name, image.id)[0]
            photo_id = attributes['photo_id']

            # Some manually added photos don't have a posted date, so pull it down if needed
            if 'posted' not in attributes:
                response = self.api.photos.getInfo(photo_id = photo_id, format = "parsed-json")
                posted = datetime.fromtimestamp(int(response['photo']['dates']['posted']))
                im.IMatchAPI.set_attributes(self.name, image.id, data = {
                    'posted' : str(posted)[:10],
                    'photo_id' : photo_id,
                    'url' : f"{im.IMatchAPI.get_application_variable("flickr_url")}/{photo_id}"
                    })
                    
            response = self.api.photos.setMeta(
                title = image.title if image.title != '' else image.name,
                description = image.full_description,  
                photo_id = photo_id
                )        

            if image.operation == IMatchImage.OP_UPDATE:
                # Update image alongside metadata
                response = self.api.replace(
                    filename = image.filename, 
                    photo_id = photo_id
                    )

            response = self.api.photos.setDates(photo_id=photo_id, date_taken=str(image.date_time), date_taken_granularity=0)
            response = self.api.photos.addTags(tags=",".join(image.keywords), photo_id=photo_id)
            response = self.api.photos.setPerms(
                photo_id=photo_id,
                is_public=self.privacy['is_public'],
                is_friend= self.privacy['is_friend'],
                is_family = self.privacy['is_family'])

            contexts = self.api.photos.getAllContexts(
                photo_id = photo_id, 
                format="parsed-json"
                )
            
            try:
                for flickr_album in contexts['set']:
                    # Is the image in the album flickr thinks its in
                    match = list(filter(lambda album: album == flickr_album['id'], image.albums))
                    if len(match) == 0:
                        # Flickr says this image is in the album (set). IMatch doesn't think it should be
                        response = self.api.photosets_removePhoto(
                            photoset_id = flickr_album['id'], 
                            photo_id = photo_id
                            )
            except KeyError:
                # No set information returned so not in any flickr albums
                pass

            for album in image.albums:
                if "set" in contexts:
                    match = list(filter(lambda set: set['id'] == album, contexts['set']))
                    if len(match) == 0:
                        response = self.api.photosets_addPhoto(
                            photoset_id = album,
                            photo_id = photo_id
                            )        
                else:
                    # No albums set, can go ahead and add
                    response = self.api.photosets_addPhoto(
                        photoset_id = album,
                        photo_id=photo_id
                        )

            try:
                for flickr_group in contexts['pool']:
                    # Is the image in the album flickr thinks its in
                    match = list(filter(lambda group: group == flickr_group['id'], image.groups))
                    if len(match) == 0:
                        # Flickr says this image is in the group (pool). IMatch doesn't think it should be
                        response = self.api.groups_pools_remove(
                            group_id=flickr_group['id'],
                            photo_id=photo_id
                            )
            except KeyError:
                # No pool information returned so not in any flickr groups
                pass

            for group in image.groups:
                if "pool" in contexts:
                    match = list(filter(lambda set: set['id'] == group, contexts['pool']))
                    if len(match) == 0:
                        response = self.api.groups_pools_add(
                            group_id = group, 
                            photo_id=photo_id
                            )        
                else:
                    # No groups set, can go ahead and add
                    response = self.api.groups_pools_add(
                        group_id = group, 
                        photo_id=photo_id
                        )   
        except flickrapi.FlickrError as fe:
            logging.error(fe)
            logging.error(response)
            sys.exit(1)

