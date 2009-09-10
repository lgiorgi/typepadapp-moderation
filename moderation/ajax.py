from urlparse import urlparse

from django import http
from django.conf import settings
from django.contrib.auth import get_user
from django.template.loader import render_to_string
from django.template import RequestContext
import simplejson as json

import typepad
from typepadapp.decorators import ajax_required
from typepadapp.models import OAuthClient, User
from moderation.models import Asset, Flag, AssetContent

from oauth import oauth


@ajax_required
def moderate(request):
    """
    Moderation actions for the moderation queue. Approve or delete. Return OK.
    """
    res = 'OK'

    asset_ids = request.POST.getlist('asset_id')

    if asset_ids is None:
        raise http.Http404

    action = request.POST.get('action', None)

    success = []
    fail = []
    ban_list = []
    for asset_id in asset_ids:
        try:
            asset = Asset.objects.get(id=asset_id)
        except:
            fail.append(asset_id)
            continue

        if action == 'approve':
            if asset.status in (Asset.FLAGGED, Asset.SUPPRESSED):
                # clear any flags too while we're at it
                Flag.objects.filter(asset=asset).delete()
                # leaving the asset as approved prevents it from being
                # flagged again
                asset.flag_count = 0
                asset.status = Asset.APPROVED
                asset.save()

            elif asset.status == Asset.MODERATED:
                content = asset.content
                tp_asset = typepad.Asset.from_dict(json.loads(content.data))

                # setup credentials of post author
                backend = urlparse(settings.BACKEND_URL)
                typepad.client.clear_credentials()
                token = oauth.OAuthToken.from_string(content.user_token)
                typepad.client.add_credentials(request.oauth_client.consumer,
                    token, domain=backend[1])

                # TODO: check for fail
                if tp_asset.type_id == 'comment':
                    typepad.client.batch_request()
                    post = typepad.Asset.get_by_url_id(tp_asset.in_reply_to.url_id)
                    typepad.client.complete_batch()
                    post.comments.post(tp_asset)
                else:
                    if content.attachment.name:
                        # file based asset; upload using signed browser upload
                        oauth_client = OAuthClient(request.application)
                        oauth_client.token = token
                        remote_url = request.application.browser_upload_endpoint
                        endpoint = oauth_client.get_file_upload_url(remote_url)
                        tp_asset.save(endpoint, group=request.group, file=content.attachment)
                    else:
                        tp_asset.save(group=request.group)

                asset.delete()

            success.append(asset_id)

        elif action in ('delete', 'ban'):
            # outright delete it?? or do we have a status for this?
            if asset.asset_id:
                if action == 'ban':
                    if asset.user_id not in ban_list:
                        # also ban this user
                        typepad.client.batch_request()
                        user_memberships = User.get_by_url_id(asset.user_id).memberships.filter(by_group=request.group)
                        typepad.client.complete_batch()

                        try:
                            user_membership = user_memberships[0]

                            if user_membership.is_admin():
                                # cannot ban/unban another admin
                                fail.append(asset_id)
                                continue

                            user_membership.block()
                            ban_list.append(asset.user_id)

                        except IndexError:
                            pass # no membership exists; ignore ban

                # we need to remove from typepad
                tp_asset = typepad.Asset.get_by_url_id(asset.asset_id)
                tp_asset.delete()

            asset.delete()
            success.append(asset_id)

        elif action == 'view':
            if asset.status in (Asset.MODERATED, Asset.SPAM):
                content = AssetContent.objects.get(asset=asset)
                data = json.loads(content.data)
                # supplement with a fake author member, since this isn't
                # populated into the POSTed data for pre-moderation/spam assets
                data['author'] = {
                    'displayName': asset.user_display_name,
                    'links': [{
                        'rel': 'avatar',
                        'href': asset.user_userpic,
                        'width': 50,
                        'height': 50
                    }]
                }
                tp_asset = typepad.Asset.from_dict(data)
                tp_asset.published = asset.ts
            else:
                typepad.client.batch_request()
                tp_asset = typepad.Asset.get_by_url_id(asset.asset_id)
                typepad.client.complete_batch()

            event = typepad.Event()
            event.object = tp_asset
            event.actor = tp_asset.author
            event.published = tp_asset.published

            # 'view' of 'permalink' causes the full content to render
            data = { 'entry': tp_asset, 'event': event, 'view': 'permalink' }
            res = render_to_string("motion/assets/asset.html", data,
                context_instance=RequestContext(request))

            return http.HttpResponse(res)

        else:
            return http.HttpResponseForbidden('{"message":"invalid request"}')

    if action == 'delete':
        res = 'You deleted %d posts.' % len(success)
    elif action == 'approve':
        res = 'You approved %d posts.' % len(success)
    elif action == 'ban':
        res = 'You banned %d users.' % len(ban_list)

    data = json.dumps({
        "success": success,
        "fail": fail,
        "message": res
    })
    return http.HttpResponse(data)
