Adding moderation to Motion
===========================

Get the moderation app:

    pip -E $VIRTUAL_ENV install -e git://github.com/sixapart/typepadapp-moderation.git#egg=typepadapp_moderation


Add the following to your urls.py:

    (r'^moderation', include('moderation.urls')),


And include the following in your local_settings.py module:

    USE_MODERATION = True
    
    if USE_MODERATION:
        from settings import INSTALLED_APPS, TEMPLATE_CONTEXT_PROCESSORS
        
        ## This is a location relative to MEDIA_ROOT and MEDIA_URL
        ## Make sure your web server has rights to create files there.
        UPLOAD_PATH = 'uploads'
        
        INSTALLED_APPS = ('moderation',) + INSTALLED_APPS

        TEMPLATE_CONTEXT_PROCESSORS += ('moderation.context_processors.globals', )

        ## Customize this setting if you wish to alter the options shown
        ## when flagging a published post or comment:        
        # REPORT_OPTIONS = [
        #     ["Option label"],
        #     ["Admin: Suppress this post immediately", 1]
        # ]
       
        ## Assign a Typepad Antispam API key here to make use of antispam
        ## filtering.
        # TYPEPAD_ANTISPAM_API_KEY = 'antispam-api-key'
        
        ## For selective moderation; enabling this feature will default
        ## moderation so that it is only done for specific users.
        # MODERATE_BY_USER = True
        
        ## For selective moderation; enabling this feature will default
        ## moderation so that it is only done for these specific post types.
        ## Types are: post, photo, link, audio, video, comment
        # MODERATE_TYPES = ('photo',)

