import os
from django.conf.urls.defaults import *


app_path = os.path.dirname(__file__)
media_dir = os.path.join(app_path, 'static')

urlpatterns = patterns('moderation.views',
    url(r'^/?$', 'DashboardView', name='dashboard'),
    url(r'^/pending/?$', 'PendingView', name='pending'),
    url(r'^/flagged/?$', 'FlaggedView', name='flagged'),
)
urlpatterns += patterns('moderation.ajax',
    url(r'^/ajax/moderate/?$', 'moderate', name='moderate'),
)
urlpatterns += patterns('',
    url(r'^/static/(?P<path>.*)/?$', 'django.views.static.serve',
        kwargs={ 'document_root': media_dir }),
)
