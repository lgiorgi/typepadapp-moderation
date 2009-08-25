from django.conf.urls.defaults import *


urlpatterns = patterns('moderation.views',
    url(r'^$', 'moderation', name='moderation'),
)