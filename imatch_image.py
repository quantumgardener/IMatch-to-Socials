from datetime import datetime
import sys
import logging

import IMatchAPI as im
import config

logging.getLogger('urllib3').setLevel(logging.INFO) # Don't want this debug level to cloud ours


class IMatchImage():

    ERROR_INDICATOR = im.IMatchAPI.COLLECTION_PINS_RED
    OP_INVALID = -1
    OP_NONE = 0
    OP_ADD = 1
    OP_UPDATE = 2
    OP_DELETE = 3

    def __init__(self, id, controller) -> None:
        self.id = id
        self.errors = []    # hold any errors raised during the process
        self.controller = controller
        self.controller.register_image(self)
        
        # -----------------------------------------------------------------------------
        # Now begins the process of collating the information to be posted alongside 
        # the image itself. This is the information we want from the version to be be 
        # posted, and later the master. Certain camera and shooting information is not
        # propogated through the versions, so we will need to walk back up the version
        # > master tree to obtain it.
        params = {
            "fields"           : "datetime,filename,name,size",
            }
        
        image_info = im.IMatchAPI.get_file_metadata([self.id], params=params)[0]
        try:
            for attribute in image_info.keys():
                # fileName is a special case. Ask for filename, get fileName in results
                match attribute:
                    case "fileName":
                        setattr(self, 'filename', image_info[attribute])
                    case "dateTime":
                        date_time = datetime.strptime(image_info[attribute],'%Y-%m-%dT%H:%M:%S')
                        setattr(self, "date_time", date_time)  
                    case other:      
                        setattr(self, attribute, image_info[attribute])  
        except KeyError:
            logging.error(f"Attribute {attribute} not returned from get_file_metadata() call")
            sys.exit(1)

        # Now grab the information from the master. This also protects us if the
        # metadata has not yet been propogated.
        master_params = {
            "fields" : "", # Setting to "" stops retrieval of more than we need
            "tagtitle" : "title",
            "tagdescription" : "description",
            "taghierarchical_keywords" : "hierarchicalkeywords",
            "varaperture" : "{File.MD.aperture}",
            "varfocal_length" : "{File.MD.focallength|value:formatted}",
            "varheadline" : "{File.MD.headline}",
            "variso" : "{File.MD.iso|value:formatted}", 
            "varlens" : "{File.MD.lens}",
            "varmodel" : "{File.MD.model}",
            "varshutter_speed" : "{File.MD.shutterspeed|value:formatted}",
            "varlatitude" : "{File.MD.gpslatitude|value:rawfrm}",
            "varlongitude" : "{File.MD.gpslongitude|value:rawfrm}"
            }

        self.master_id = im.IMatchAPI.get_master_id(self.id)
        if self.master_id == None:
            # We are the master, use original id
            self.master_id = id
        image_info = im.IMatchAPI.get_file_metadata([self.master_id],master_params)[0]
        try:
            for attribute in image_info.keys():
                setattr(self, attribute, image_info[attribute])  # remove prefix for our purposes
        except KeyError:
            logging.error(f"Attribute {attribute} not returned from get_file_metadata() call")
            sys.exit(1)
        
        # Retrieve the list of categories the image belongs to.
        self.categories = im.IMatchAPI.get_file_categories([self.id], params={
            'fields' : 'path,description'}
            )[self.id]
        
        # Set the operation for this file.
        self.operation = IMatchImage.OP_NONE
        if self.is_valid:
            if not self.is_on_platform:
                self.operation = IMatchImage.OP_ADD
            else:
                # Check collections for overriding instructions
                if self.wants_update and self.wants_delete:
                    # We have conflicting instructions. 
                    self.errors.append(f"Conflicting instructions. Images is in both {IMatchImage.config.DELETE_CATEGORY} and IMatchImage.config.UPDATE_CATEGORY categories.")
                    self.operation = IMatchImage.OP_INVALID
                else:
                    if self.wants_update:
                        self.operation = IMatchImage.OP_UPDATE
                    if self.wants_delete:
                        self.operation = IMatchImage.OP_DELETE
        else:
            self.operation = IMatchImage.OP_INVALID

    def __repr__(self) -> str:
        return vars(self)

    def __str__(self) -> str:
        return f"{type(self).__name__}(id: {self.id}, filename: {self.filename}, size: {self.size})"
       
    def prepare_for_upload(self) -> None:
        """Build variables ready for uploading."""
        self.keywords = set()  # These are the keywords to output. self.hierachy_keywords is what comes in
        for keyword in self.hierarchical_keywords:
            splits = keyword.split("|")
            match splits[0]:
                case 'art':
                    for artform in splits:
                        self.add_keyword(artform)
                case 'genre':
                    # Genre is tagged with itself and with "photography appended"
                    for genre in splits[1:]:
                        self.keywords.add(genre)
                        if genre != 'astrophotography':
                            self.add_keyword(genre+"photography")
                case 'Location':
                    try:
                        self.add_keyword(splits[3]) # town
                        self.add_keyword(splits[4]) # location
                    except IndexError:
                        pass
                case 'nature':
                    for nature in splits[1:]:
                        self.add_keyword(nature) # Add each keyword
                case 'toys and games':
                    for nature in splits[1:]:
                        self.add_keyword(nature) # Add each keyword

        # Add certain categories as keywords
        for categories in self.categories:
            splits = categories['path'].split("|")
            match splits[0]:
                case 'Image Characteristics':
                    self.add_keyword(splits.pop()) # Get the leaf

    def add_keyword(self, keyword) -> str:
        """Ensure all keywords are added without spaces"""
        no_spaces_keyword = keyword.replace(" ","")
        no_ampersand_keyword = no_spaces_keyword.replace("&","-and-")
        no_dash_keyword = no_ampersand_keyword.replace("-","")
        self.keywords.add(no_dash_keyword)
        return no_dash_keyword
    
    def is_image_in_category(self, search_category) -> bool:
        found = False
        for category in self.categories:
            if category['path'] == search_category:
                found = True
                break
        return found

    @property
    def is_master(self) -> bool:
        return self.id == self.master_id
    
    @property
    def is_version(self) -> bool:
        return not self.is_master()
    
    @property
    def is_on_platform(self) -> bool:
        raise NotImplementedError("Subclasses must implement is_on_platform()")
    
    @property
    def camera_info(self) -> str:
        """Standardise a basic way of presenting camera information on a single line"""
        camera_info = []
        try:
            match self.model:
                case "UltraFractal":
                    camera_info.append("Digital image generated in Ultrafractal.")
                case "ScanSnap S1300":
                    camera_info.append("Digitised from a print scanned using a Fujitsu ScanSnap S1300.")
                case other:
                    camera_info.append(self.model)
        except AttributeError:
            pass
        if self.lens.strip() != '':
            camera_info.append(self.lens)

        return " | ".join(camera_info) if len(camera_info) > 0 else ''

    @property
    def shooting_info(self) -> str:
        """Standardise a basic way of presenting shooting information on a single line"""
        shooting_info = []

        try:
            if self.iso != '':
                shooting_info.append(f"ISO {self.iso}")
        except AttributeError:
            pass

        try:
            if self.shutter_speed != '':
                shooting_info.append(f"{self.shutter_speed} sec")
        except AttributeError:
            pass

        try:
            shooting_info.append('f/{0:.3g}'.format(float(self.aperture)))
        except (AttributeError, ValueError):
            pass

        try:
            shooting_info.append(f"{self.focal_length}") 
        except AttributeError:
            pass
           
        return " | ".join(shooting_info) if len(shooting_info) > 0 else ''
   
    @property
    def is_valid(self) -> bool:
        for attribute in ['title', 'description']:
            try:
                if getattr(self, attribute).strip() == '':
                    self.errors.append(f"missing {attribute}")
            except AttributeError:
                self.errors.append(f"missing {attribute}")
        genre_ok = False
        for keyword in self.hierarchical_keywords:
            splits = keyword.split("|")
            match splits[0]:
                case 'genre':
                    genre_ok = True
        if not genre_ok:
            self.errors.append(f"missing genre")
        if self.is_master:
            self.errors.append("is master")
        return len(self.errors) == 0

    @property
    def controller(self):
        if self._controller is None:
            raise ValueError("Controller has not been set")
        else:
            return self._controller

    @controller.setter
    def controller(self, controller):
        self._controller = controller

    @property
    def wants_delete(self) -> bool:
        return self.is_image_in_category(
            im.IMatchUtility.build_category([
                config.ROOT_CATEGORY,
                self._controller.name,
                config.DELETE_CATEGORY
                ])
            )

    @property
    def wants_update(self) -> bool:
        return self.is_image_in_category(
            im.IMatchUtility.build_category([
                config.ROOT_CATEGORY,
                self._controller.name,
                config.UPDATE_CATEGORY
                ])
            )

        
        
        

