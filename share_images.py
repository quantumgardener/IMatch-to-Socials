from IMatchAPI import IMatchAPI
import flickr
import pixelfed
from pprint import pprint
import sys
import logging
logging.basicConfig(
    level = logging.INFO,
    format = '%(levelname)8s | %(message)s'
    )

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

    IMatchAPI()             # Perform initial connection
    
    # Gather all image information
    for platform in Factory.platforms.keys():
        logging.info( "--------------------------------------------------------------------------------------")
        logging.info(f"{platform}: Gathering images from IMatch.")
        controllers[platform] = Factory.get_controller_class(platform)()
        for image_id in IMatchAPI().get_files_in_category(f"Socials|{platform}"):
            image = Factory.build_image(image_id, platform)
            controllers[platform].add_image(image)
        logging.info(f"{platform}: {controllers[platform].stats['total']} images gathered from IMatch.")

        controllers[platform].classify_images()
        controllers[platform].add()
        controllers[platform].update()
        #controllers[platform].delete()
        controllers[platform].list_errors()
        controllers[platform].summarise()

    stats = {}
    for platform in Factory.platforms.keys():
        platform_stats = controllers[platform].stats
        for stat in platform_stats:
            try:
                stats[stat] += platform_stats[stat]
            except KeyError:
                stats[stat] = platform_stats[stat]
            
    logging.info( "--------------------------------------------------------------------------------------")
    logging.info(f"Final summary of images processed")
    for val in stats.keys():
        logging.info(f"-- {stats[val]} {val} images")
    
    logging.info("--------------------------------------------------------------------------------------")
    logging.info("Done.")


