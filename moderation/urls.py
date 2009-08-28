import os
from django.conf.urls.defaults import *


app_path = os.path.dirname(__file__)
media_dir = os.path.join(app_path, 'static')

urlpatterns = patterns('moderation.views',
    url(r'^/?$', 'ModerationView', name='moderation'),
)
urlpatterns += patterns('',
    url(r'^/static/(?P<path>.*)/?$', 'django.views.static.serve',
        kwargs={ 'document_root': media_dir }),
)
