import os

# This class accesses a file containing the list of additional
# keyword hierarchies to include as valid
class Keyword_Manager:

    keyword_categories = []

    def __init__(self) -> None:
        pass

    @classmethod
    def keyword_list(cls):
        if len(cls.keyword_categories) == 0:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'keyword_categories.txt'), 'r') as file:
                cls.keyword_categories = [line.strip() for line in file.readlines()];
        return cls.keyword_categories