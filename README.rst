Nothing to see here yet.


Add moderation to Motion
====

Get the moderation app:

    pip -E $VIRTUAL_ENV install -e git+ssh://git@github.com/sixapart/moderation.git#egg=moderation


To your INSTALLED_APPS add:

    'moderation',


Add the following to your urls.py:

    (r'^moderation', include('moderation.urls')),


You'll also need to add an UPLOAD_PATH to your settings like so: