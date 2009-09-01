from django import http
from django.conf import settings
from django.contrib.auth import get_user
from django.template.loader import render_to_string
from django.template import RequestContext
import simplejson as json

from typepadapp.decorators import ajax_required
from moderation.models import Asset


@ajax_required
def moderate(request):
    """
    Add this item to the user's favorites. Return OK.
    """
    res = 'OK'
    
    asset_id = request.POST.get('asset_id')
    if not asset_id:
        raise http.Http404
    asset = Asset.objects.get(id=asset_id)

    action = request.POST.get('action', 'approve')
    if action == 'approve':
        asset.status = 4
        asset.save()
        res = 'Post approved.'

    return http.HttpResponse(res)