# IMatch-Python-API

**IMatch-Python-API** is a Python wrapper for the IMatch API functions. [IMatch](https://www.photools.com) is a powerful digital asset management systems for managing photos and their metadata. I've been using it since forever. One of the features is a full backend API for manipulating information in the database using scripts.

> **This is a hobby project.** I've created it for my own purposes to assist me upload images to my pixelfed and flickr accounts. The code will always reflect my personal needs. You are free to fork your own copy. My accounts are:
> - [@dcbuchan@pixelfed.au](https://pixelfed.au/dcbuchan)
> - [dcbuchan](https://www.flickr.com/photos/dcbuchan/)

Obviously you will need some programming chops to work with what is presented here. I've commented the code extensively. Take it and play, but be sure you have backups of everything. This code works for my setup. It may not work for yours.

## Scripts

All scripts require Python 3.10 or later.

| Script                    | What it does                                                  | Requirements                                                                       |
| ------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| **IMatchAPI.py**          | API wrapper that simplifies calls to IMatch                   | Your own copy of IMatch                                                            |
| **IMatch to Pixelfed.py** | Code to pull infomration about images, and upload to Pixelfed | [Mastodon.py](https://pypi.org/project/Mastodon.py/) and your own Pixelfed app key |
## Further documentation
Furher documentation, including explanation on how I've set up my IMatch database for this to work can be found at [IMatch to Socials](https://quantumgardener.info/notes/imatch-to-socials).


> The pixelfed example could be used for any Mastodon instance.

