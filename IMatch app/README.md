# IMatch-to-Socials IMatch app

The "IMatch app" embeds the Python scripts for uploading to socials into IMatch so that you can run it from within IMatch itself.

There are options for all platform uploads, and individual platforms. Nothing will be displayed until the script completes if run as an app.

## Application Setup
1. Copy this whole folder into your `C:\ProgramData\photools.com\imatch6\webroot\user` folder.
2. Create a new **application** variable
    - Name = `imatch_to_socials_python_script_path`
    - String Value = path to where `share_images.py` is stored

    ![Application Variables Screenshot](https://github.com/quantumgardener/IMatch-to-Socials/blob/main/IMatch%20app/application_variables_screenshot.png)
3. Restart IMatch

Of course, you will also need to provide your api keys for the scripts to work, along with your defaults for the other variables listed.
- `flickr_apikey`
- `flickr_apisecret`
- `mastodon_token`
- `mastodon_url` 
- `pixelfed_token`
- `pixelfed_url` 


