## Pre-requisites
# pip3 install Mastodon.py

from imatch_image import IMatchImage
from platform_base import PlatformController
import mastodon
from IMatchAPI import IMatchAPI
from pprint import pprint
import sys
import logging
logging.basicConfig(level=logging.INFO)

MB_SIZE = 1048576

class PixelfedImage(IMatchImage):

    __MAX_SIZE = 15 * MB_SIZE

    def __init__(self, id) -> None:
        super().__init__(id)
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
        for attribute in ['title', 'description', 'headline']:
            try:
                if getattr(self, attribute).strip() == '':
                    self.errors.append(f"-- missing '{attribute}'.")
            except AttributeError:
                self.errors.append(f"-- missing '{attribute}'.")
        if self.size > PixelfedImage.__MAX_SIZE:
            logging.error(f'Skipping: {self.name} is too large to upload: {self.size/MB_SIZE:2.1f} MB. Max is {PixelfedImage.__MAX_SIZE/MB_SIZE:2.1f} MB.')
            self.errors.append(f"-- {self.size/MB_SIZE:2.1f} MB exceeds max {PixelfedImage.__MAX_SIZE/MB_SIZE:2.1f} MB.")
        return len(self.errors) == 0

    @property
    def is_on_platform(self) -> bool:
        res = IMatchAPI.get_attributes("pixelfed", self.id)
        return len(res) != 0

class PixelfedController(PlatformController):
    
    def __init__(self) -> None:
        super().__init__()

    def connect(self):
        if self.api is not None:
            return
        else:
            # Create a Mastodon instance. Get secrets from IMatch
            # https://www.photools.com/help/imatch/index.html#var_basics.htm
            try:
                logging.info("pixelfed: Connecting to platform.")
                pixelfed = mastodon.Mastodon(
                    access_token = IMatchAPI.get_application_variable("pixelfed_token"),
                    api_base_url = IMatchAPI.get_application_variable("pixelfed_url")
                )
            except mastodon.MastodonUnauthorizedError:
                print('unuathorised')
                sys.exit()

            # Fetch my account details. Serves as a good check of connection details
            # before bothering to upload images. If it fails here, nothing else will work.
            try:
                logging.info("pixelfed: Verifying pixelfed account credentials.")
                account = pixelfed.account_verify_credentials()
                logging.info(f"pixelfed: Verified. Connected to {account['url']}.")
            except mastodon.MastodonNetworkError as mne:
                logging.error(f"pixelfed: Unable to obtain account details. Check URL {IMatchAPI.get_application_variable("pixelfed_url")}.")
                print (mne)
                sys.exit()
            except mastodon.MastodonAPIError:
                logging.error("pixelfed: Unable to access credentials. Check token.")
                sys.exit()
            except Exception as e:
                print(f"pixelfed: An unexpected error occurred: {e}")
                sys.exit()

            ## Get the default visibility for posts. Can be one of:
            # public = Visible to everyone, shown in public timelines.
            # unlisted = Visible to public, but not included in public timelines.
            # private = Visible to followers only, and to any mentioned users.
            # direct = Visible only to mentioned users.

            self._visibility = IMatchAPI.get_application_variable("pixelfed_visibility")
            self.api = pixelfed

    def platform_add(self):

        if len(self.images_to_add) == 0:
            return  #N Nothing to see here
        
        self.connect()

        progress_counter = 1
        progress_end = len(self.images_to_add)
        for image in self.images_to_add:
            try:
                # Prepare the image for attaching to the status. In Mastodon, "posts/toots" are all status
                # Upload the media, then the status with the media attached. 
        
                logging.info(f'pixelfed: Uploading ({progress_counter}/{progress_end}) "{image.title}" from "{image.filename}"')
                media = self.api.media_post(  
                    media_file = image.filename,
                    description= image.headline
                )

                # Create a new status with the uploaded image                   
                status = self.api.status_post(
                    status     = image.full_description,
                    media_ids  = media, 
                    visibility = self._visibility
                )

                #Update the image in IMatch by adding the attributes below.
                IMatchAPI().set_attributes("pixelfed", image.id, data = {
                    'posted' : status['created_at'].isoformat()[:10],
                    'media_id' : media['id'],
                    'status_id' : status['id'],
                    'url' : status['url']
                    })

                progress_counter += 1

            except KeyError:
                logging.error("Missed validating an image field somewhere.")
                sys.exit()
            except mastodon.MastodonAPIError as mae:
                logging.error(f"An API error occurred: {mae}.")
                sys.exit()
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")
                sys.exit()


