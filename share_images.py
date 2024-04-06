from IMatchAPI import IMatchAPI
import flickr
import pixelfed
from pprint import pprint
import sys
import logging
logging.basicConfig(level=logging.INFO)

class Factory():

    platforms = {
        'flickr' : {
            'image' : flickr.FlickrImage,
            'controller' : flickr.FlickrController,
        },
        'pixelfed' : {
            'image' : pixelfed.PixelfedImage,
            'controller' : pixelfed.PixelfedController
        }
    }

    def __init__(self) -> None:
        pass
        
    @classmethod
    def build_image(cls, id, platform):
        
        try:
            return cls.platforms[platform]['image'](id)
        except KeyError:
            print(f"{cls.__name__}.build(platform): '{platform}' is an unrecognised platform. Valid options are {cls.platforms}.")
            sys.exit()
        
    @classmethod
    def get_controller_class(cls, platform):

        try:
            return cls.platforms[platform]['controller']
        except KeyError:
            print(f"{cls.__name__}.build(platform): '{platform}' is an unrecognised platform. Valid options are {cls.platforms}.")
            sys.exit()
          
if __name__ == "__main__":

    if not sys.version_info >= (3, 10):
        print(f"Python version 3.10 or later required. You are running with version {sys.version_info.major}.{sys.version_info.minor}")
        sys.exit()


    # Retreive the complete list of Socials files from IMatch for all known
    # platforms. Within IMatch, files are in the Socials|{platform} category
    # or subcategories.

    ##pprint(IMatchAPI().get_imatch("v1/collections",params={'id' : 'all','fields':'id,path'}))

    images = []             # main image store
    controllers = {}

    for platform in Factory.platforms.keys():
        logging.info(f"{platform}: Gathering images from IMatch.")
        controllers[platform] = Factory.get_controller_class(platform)()
        for image_id in IMatchAPI().get_files_in_category(f"Socials|{platform}"):
            image = Factory.build_image(image_id, platform)
            controllers[platform].add_image(image)
        logging.info(f"{platform}: {controllers[platform].stats['total']} images to process from IMatch.")

        controllers[platform].prepare_images()
        controllers[platform].platform_add()

        logging.info(f"{platform}: Processing complete.")
        
    print("Done.")


