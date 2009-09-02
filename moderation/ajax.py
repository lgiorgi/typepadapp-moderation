from urlparse import urlparse

from django import http
from django.conf import settings
from django.contrib.auth import get_user
from django.template.loader import render_to_string
from django.template import RequestContext
import simplejson as json

import typepad
from typepadapp.decorators import ajax_required
from moderation.models import Asset, Flag, AssetContent

from oauth import oauth


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
    if not asset:
        raise http.Http404

    action = request.POST.get('action', 'approve')
    if action == 'approve':
        if asset.status == Asset.FLAGGED:
            # clear any flags too while we're at it
            Flag.objects.filter(asset=asset).delete()
            # leaving the asset as approved prevents it from being
            # flagged again
            asset.flag_count = 0
            asset.status = Asset.APPROVED
            asset.save()
        elif asset.status == Asset.MODERATED:
            # TODO: we need to push this to TypePad
            content = AssetContent.objects.get(asset=asset)

            tp_asset = typepad.Asset.from_dict(json.loads(content.data))
            # if content.attachment:
            #     tp_asset.file = content.attachment

            # setup credentials of post author
            backend = urlparse(settings.BACKEND_URL)
            typepad.client.clear_credentials()
            token = oauth.OAuthToken.from_string(content.user_token)
            typepad.client.add_credentials(request.oauth_client.consumer,
                token, domain=backend[1])

            print "saving tp_asset"
            # TODO: check for fail
            try:
                tp_asset.save(group=request.group)
            except Exception, ex:
                print "got an exception: %s" % ex
                raise ex

            print "deleting local asset"
            asset.delete()
        res = 'Post approved.'
    elif action == 'delete':
        # outright delete it?? or do we have a status for this?
        asset.delete()
        res = 'Post deleted.'
    else:
        return http.HttpResponseForbidden("invalid request")

    return http.HttpResponse(res)
