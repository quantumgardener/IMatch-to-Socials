# IMatch-to-Socials

**IMatch-to-socials** automates uploading images from [IMatch](https://www.photools.com) to flickr and pixelfed. IMatch is a powerful digital asset management systems for managing photos and their metadata. I've been using it since forever. One of the features is a full backend API for manipulating information in the database using scripts.

> **This is a hobby project.** I've created it for my own purposes to assist me upload images to my pixelfed and flickr accounts. The code will always reflect my personal needs. You are free to fork your own copy. My accounts are:
> - [@dcbuchan@pixelfed.au](https://pixelfed.au/dcbuchan)
> - [dcbuchan](https://www.flickr.com/photos/dcbuchan/)

**Only a small set of API endpoint calls are catered for. Just those I need for now.**

## WARNING! WARNING! WARNING!
**BE REALLY CAREFUL. CODE MODIFIES IMATCH AND SOCIAL PLATFORMS**. I'm not responsible for any loss of your data.

Obviously you will need some programming chops to work with what is presented here. I've commented the code extensively. Take it and play, but be sure you have backups of everything. This code works for my setup. It may not work for yours.

## Script Dependencies

All scripts require Python 3.10 or later.

The main script is share_images.py.

| Script                    | What it does                                                  | Requirements                                                                       |
| ------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| **IMatchAPI.py**          | API wrapper that simplifies calls to IMatch                   | Your own copy of IMatch                                                            |
| **pixelfed.py** | Code to pull information about images, and upload to Pixelfed | [Mastodon.py](https://pypi.org/project/Mastodon.py/) and your own Pixelfed app key |
| **flickr.py**   | Code to manage uploads to flickr                              | [flick api](https://stuvel.eu/software/flickrapi/) and "pip install tzdata"        |

## Further documentation
Furher documentation, including explanation on how I've set up my IMatch database for this to work can be found at [IMatch to Socials](https://quantumgardener.info/notes/imatch-to-socials).


> The pixelfed example could be used for any Mastodon instance.

