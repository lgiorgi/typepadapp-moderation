Settings
========

The Moderation app for TypePad Motion provides several optional settings you
can configure to customize the behavior to suit your community. The following
Django settings are specific to the Moderation app. You can assign them in
your Django project's ``settings.py`` file.

There are two settings that deserve special mention: ``MODERATE_BY_USER`` and
``MODERATE_TYPES``. These settings configure the Moderation app to selectively
moderate posted content, instead of moderating everything. When you set one or
the other, the effect is obvious, but when used together it is not obvious how
they work together. Consider this configuration::

    MODERATE_TYPES = ('photo', 'audio', 'post', 'link', 'video')
    MODERATE_BY_USER = True

In this case, we are specifying that the Moderation app should pre-moderate
everything but comments. But we are also configuring to moderate specific
users. In this case, the user moderation feature takes precedent: all posts,
regardless of type -- even comments -- will be moderated if a user is marked
to be moderated (you set this status on their Motion member profile page). And
for members that are not specifically marked for moderation, they will be
subject to pre-moderation for non-comment posts.


USE_MODERATION
--------------

This is the master switch for the Moderation app. This setting must be
assigned a "True" value in order for the Moderation app to run properly. In
addition to enabling this setting, the Moderation app should be added to the
list of Django's ``INSTALLED_APPS``. For a typical Motion installation, you
should add this block to your Django project's ``settings.py`` file::

    USE_MODERATION = True

    if USE_MODERATION:
        INSTALLED_APPS = ('moderation',) + INSTALLED_APPS

        TEMPLATE_CONTEXT_PROCESSORS += ('moderation.context_processors.globals', )

        # Path for uploaded files; relative to MEDIA_ROOT
        UPLOAD_PATH = 'uploads'

        # Any other Moderation-specific settings should be
        # assigned here...

By conditioning the other settings for Moderation in this way, you can easily
enable and disable the whole feature by changing the ``USE_MODERATION``
setting.

You will also need to customize your ``urls.py`` file for your project to
include the urls necessary for Moderation. The following block can be added to
your ``urls.py`` module::

    import os
    from django.conf import settings

    ## (your existing urlpatterns would be here)

    if settings.USE_MODERATION:
        urlpatterns += patterns('',(r'^moderation', include('moderation.urls')))
        upload_path = os.path.join(settings.MEDIA_ROOT, settings.UPLOAD_PATH)
        urlpatterns += patterns('', url(r'^static/%s/(?P<path>.*)/?$' \
            % settings.UPLOAD_PATH,
            'django.views.static.serve',
            kwargs={ 'document_root': upload_path }))

Note that if you are using Apache and mod_wsgi, you will need to create an
Alias directive to serve static files::

    Alias /static/moderation /path/to/moderation/static

You also need an Alias for serving uploaded files (substitute "uploads" with
the any custom value you assign to the ``UPLOAD_PATH`` Moderation app
setting)::

    Alias /static/uploads /path/to/media_root/uploads


MODERATE_BY_USER
----------------

Set to "True" to enable selective moderation (by default, this is False). When
this is off, all posts made by users are moderated and held for a moderator to
approve before appearing on the site. When ``MODERATE_BY_USER`` is enabled,
posts are not pre-moderated globally; admins can selectively flag users (from
their Motion profile page) so their posts are moderated. Example::

    MODERATE_BY_USER = True


MODERATE_TYPES
--------------

Enabling this feature will cause only specific post types to be pre-moderated.
Post types are "post", "photo", "link", "audio", "video" and "comment".
Example::

    MODERATE_TYPES = ('photo', 'audio')

This will cause the Moderation app to only pre-moderate photo and audio posts.

If you want to pre-moderate everything except for comments, you can configure
this setting like this::

    MODERATE_TYPES = ('post', 'photo', 'link', 'audio', 'video')

If you want to disable pre-moderation altogether, you can assign None:

    MODERATE_TYPES = None


UPLOAD_PATH
-----------

This setting is required and must identify a directory that is relative to the
``MEDIA_ROOT`` setting. This will be the path where photo and audio files are
uploaded when pre-moderation is in effect. Example::

    UPLOAD_PATH = 'uploads'

The directory that this path references must exist and must be writeable by
the Django process account. If it is not, uploads will fail. Be sure to test
file uploads in general after enabling moderation.

Also note that your ``MEDIA_ROOT`` setting may require a full file path; in
some cases this is assigned a value with a relative portion in it
('/path/to/../dir'); if you are having trouble with moderation and uploaded
files, try assigning a full path for ``MEDIA_ROOT``.


REPORT_OPTIONS
--------------

A list of canned reasons for flagging a given post or comment. This list is
shown to users when they click the "flag" icon shown for posts. Each element
here is an array with two values: the label for the option and an optional
threshold value. The threshold identifies the number of end-user reports that
will cause a post or comment to be suppressed (hidden for posts, grayed-out
for comments) on the site. Example::

    REPORT_OPTIONS = [
        ['Poor taste'],
        ['Sexual material'],
        ['Copyright infringement'],
        ['Rick-roll', 10],
        ['Terms of service violation', 5],
        ['Admin: Immediately suppress this post', 1],
    ]

Note that any reason that is prefixed with "Admin:" is only shown to
administrators. It is not recommended to assign a low suppression threshold
for options shown to regular users, but it is useful for administrator-only
options, since it will have immediate effect at hiding the post from the site,
but not deleting it altogether.

You can also hide any option by using a "-" at the start of the label. This
will prevent it from showing as an option to the user, but it will still be
available for reference for existing moderation reports that used it.


TYPEPAD_ANTISPAM_API_KEY
------------------------

This setting will enable the use of the TypePad AntiSpam service for filtering
incoming posts and comments for spam. This should be assigned a TypePad
AntiSpam API key; these are free for unlimited use. You can obtain an API key
from the `TypePad AntiSpam web site <http://antispam.typepad.com/>`_.
Example::

    TYPEPAD_ANITSPAM_API_KEY = "your_api_key"

To use this setting, you will need to install the Python ``akismet`` module.
You can install this module by running the following command on your web
server::

    sudo easy_install akismet

Note that administrators and featured users are not subject to antispam
scoring and filtering.
