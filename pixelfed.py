## Pre-requisites
# pip3 install Mastodon.py
import sys
import logging

import mastodon

from imatch_image import IMatchImage
from platform_base import PlatformController
import IMatchAPI as im
import config


class PixelfedImage(IMatchImage):

    __MAX_SIZE = 15 * config.MB_SIZE

    def __init__(self, id, platform) -> None:
        super().__init__(id, platform)
        self.alt_text = None

    def prepare_for_upload(self) -> None:
        """Build variables ready for uploading."""
        super().prepare_for_upload()

        tmp_description = [f"{self.title} -- {self.description} (Taken {self.date_time.strftime("%#d %B %Y")})"]
        tmp_description.append('')
        if len(self.keywords) > 0:
            tmp_description.append(" ".join(["#" + keyword for keyword in self.keywords]))  # Ensure pixelfed keywords are hashtags
            tmp_description.append('')

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
        for attribute in ['headline']:
            try:
                if getattr(self, attribute).strip() == '':
                    self.errors.append(f"missing {attribute}")
            except AttributeError:
                self.errors.append(f"missing {attribute}")
        if self.size > PixelfedImage.__MAX_SIZE:
            logging.error(f'{self.controller.name}: Skipping {self.name} is too large to upload: {self.size/config.MB_SIZE:2.1f} MB. Max is {PixelfedImage.__MAX_SIZE/config.MB_SIZE:2.1f} MB.')
            print(f'{self.controller.name}: Skipping {self.name} is too large to upload: {self.size/config.MB_SIZE:2.1f} MB. Max is {PixelfedImage.__MAX_SIZE/config.MB_SIZE:2.1f} MB.')
            self.errors.append(f"file too large")
        return len(self.errors) == 0 and result

    @property
    def is_on_platform(self) -> bool:
        res = im.IMatchAPI.get_attributes("pixelfed", self.id)
        return len(res) != 0

class PixelfedController(PlatformController):
    
    def __init__(self, platform) -> None:
        super().__init__(platform)

    def connect(self):
        if self.api is not None:
            return
        else:
            # Create a Mastodon instance. Get secrets from IMatch
            # https://www.photools.com/help/imatch/index.html#var_basics.htm
            try:
                print(f"{self.name}: Work to do -- Connecting to platform.")
                pixelfed = mastodon.Mastodon(
                    access_token = im.IMatchAPI.get_application_variable("pixelfed_token"),
                    api_base_url = im.IMatchAPI.get_application_variable("pixelfed_url")
                )
            except mastodon.MastodonUnauthorizedError:
                logging.error(f"{self.name} unauthorised for connection.")
                sys.exit(1)

            # Fetch my account details. Serves as a good check of connection details
            # before bothering to upload images. If it fails here, nothing else will work.
            try:
                print(f"{self.name}: Verifying pixelfed account credentials.")
                account = pixelfed.account_verify_credentials()
                print(f"{self.name}: Verified. Connected to {account['url']}.")
            except mastodon.MastodonNetworkError as mne:
                logging.error(f"{self.name}: Unable to obtain account details. Check URL {im.IMatchAPI.get_application_variable("pixelfed_url")}.")
                logging.error(mne)
                sys.exit(1)
            except mastodon.MastodonAPIError:
                logging.error(f"{self.name}: Unable to access credentials. Check token.")
                sys.exit(1)
            except Exception as e:
                logging.error(f"{self.name}: An unexpected error occurred: {e}")
                sys.exit(1)

            ## Get the default visibility for posts. Can be one of:
            # public = Visible to everyone, shown in public timelines.
            # unlisted = Visible to public, but not included in public timelines.
            # private = Visible to followers only, and to any mentioned users.
            # direct = Visible only to mentioned users.

            self._visibility = im.IMatchAPI.get_application_variable("pixelfed_visibility")
            self.api = pixelfed

    def commit_add(self, image):
        """Make the api call to commit the image to the platform, and update IMatch with reference details"""
        try:
            # Prepare the image for attaching to the status. In Mastodon, "posts/toots" are all status
            # Upload the media, then the status with the media attached. 
            media = self.api.media_post(  
                media_file = image.filename,
                description= image.headline
            )

            # Create a new status with the uploaded image                   
            status = self.api.status_post(
                status = image.full_description,
                media_ids = media, 
                visibility = self._visibility
            )

            # Update the image in IMatch by adding the attributes below.
            im.IMatchAPI().set_attributes(self.name, image.id, data = {
                'posted' : status['created_at'].isoformat()[:10],
                'media_id' : media['id'],
                'status_id' : status['id'],
                'url' : status['url']
                })
        except KeyError:
            logging.error(f"{self.name}: Missed validating an image field somewhere.")
            sys.exit()
        except mastodon.MastodonAPIError as mae:
            logging.error(f"{self.name}: An API error occurred: {mae}.")
            sys.exit()
        except Exception as e:
            logging.error(f"{self.name}: An unexpected error occurred: {e}")
            sys.exit()

    def commit_delete(self, image):
        """Make the api call to delete the image from the platform"""
        try:
            attributes = im.IMatchAPI().get_attributes(self.name, image.id)[0]
            status_id = attributes['status_id']

            # Update the status with new text
            status = self.api.status_delete(
                id = status_id,
            )
        except KeyError:
            logging.error(f"{self.name}: Missed validating an image field somewhere.")
            sys.exit()
        except mastodon.MastodonAPIError as mae:
            logging.error(f"{self.name}: An API error occurred: {mae}.")
            sys.exit()
        except Exception as e:
            logging.error(f"{self.name}: An unexpected error occurred: {e}")
            sys.exit()

    def commit_update(self, image):
        """Make the api call to update the image on the platform"""
        try:
            attributes = im.IMatchAPI().get_attributes(self.name, image.id)[0]
            media_id = attributes['media_id']
            status_id = attributes['status_id']

            media = self.api.media_update(
                id = media_id,  
                description= image.headline
            )

            # Update the status with new text
            status = self.api.status_update(
                id = status_id,
                status = image.full_description,
                media_ids = media, 
            )
        except KeyError:
            logging.error(f"{self.name}: validating an image field somewhere.")
            sys.exit()
        except mastodon.MastodonAPIError as mae:
            logging.error(f"{self.name}: API error occurred: {mae}.")
        except Exception as e:
            logging.error(f"{self.name}: unexpected error occurred: {e}")
            sys.exit()
    

