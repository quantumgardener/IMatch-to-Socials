from pprint import pprint
import logging
logging.basicConfig(level=logging.INFO)

class PlatformController():

    def __init__(self) -> None:
        self.images = set()
        self.images_to_add = set()
        self.images_to_delete = set()
        self.images_to_update = set()
        self.invalid_images = set()
        self.api = None  # Holds the platform api connection once active

    def connect(self):
        """Upload and add image to platform"""
        raise NotImplementedError("Subclasses must implement this for their specific platnform.")

    def add_image(self, image):
        image.controller = self
        self.images.add(image)
      
    def platform_add(self):
        """Upload and add image to platform"""
        raise NotImplementedError("Subclasses must implement this for their specific platnform.")

    def platform_delete(self):
        """Delete image from platform"""
        raise NotImplementedError("Subclasses must implement this for their specific platnform.")

    def platform_update(self):
        """Update image on platform"""
        raise NotImplementedError("Subclasses must implement this for their specific platnform.")

    def prepare_images(self):
        for image in self.images:
            if not image.is_final:
                if image.is_valid:               
                    image.prepare_for_upload()
                    if not image.is_on_platform:
                        self.images_to_add.add(image)
                    else:
                        self.images_to_update.add(image)
                else:
                    self.invalid_images.add(image)
            else:
                pass

    @property
    def stats(self):
        return {
            "platform" : type(self).__name__,
            "total" : len(self.images),
            "adds" : len(self.images_to_add),
            "deletes" : len(self.images_to_delete),
            "updates" : len(self.images_to_update),
            "invalid" : len(self.invalid_images),
            "ignores" : len(self.images)
                        - len(self.images_to_add)
                        - len(self.images_to_delete)
                        - len(self.images_to_update)
                        - len(self.invalid_images)
        }