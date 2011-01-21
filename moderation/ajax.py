# Copyright (c) 2009-2011 Six Apart Ltd.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of Six Apart Ltd. nor the names of its contributors may
#   be used to endorse or promote products derived from this software without
#   specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from django import http
from django.conf import settings
from django.contrib.auth import get_user
from django.template.loader import render_to_string
from django.template import RequestContext
import simplejson as json

import typepad

from typepadapp.decorators import ajax_required
from typepadapp.models import User
from typepadapp import signals

from moderation.models import Queue, Flag, QueueContent, Blacklist
from moderation import models


@ajax_required
def moderate(request):
    """
    Moderation actions for the moderation queue. Approve or delete. Return OK.
    """

    if not hasattr(request, 'user'):
        typepad.client.batch_request()
        request.user = get_user(request)
        typepad.client.complete_batch()

    if not (request.user.is_authenticated() and \
        request.user.is_superuser):
        return http.HttpResponseForbidden()

    res = 'OK'

    item_ids = request.POST.getlist('item_id')

    if item_ids is None:
        raise http.Http404

    action = request.POST.get('action', None)

    success = []
    fail = []
    ban_list = []
    for item_id in item_ids:
        queue = None
        user = None
        if action.endswith('_user'):
            try:
                user = Blacklist.objects.get(user_id=item_id)
            except Blacklist.DoesNotExist:
                if action == 'approve_user':
                    success.append(item_id)
                    continue
                else:
                    fail.append(item_id)
                    continue
        else:
            try:
                queue = Queue.objects.get(id=item_id)
            except:
                fail.append(item_id)
                continue

        if action == 'approve':
            queue.approve()
            success.append(item_id)

        elif action in ('delete', 'ban'):
            # outright delete it?? or do we have a status for this?
            if action == 'ban':
                if asset.user_id not in ban_list:
                    # also ban this user
                    typepad.client.batch_request()
                    user_memberships = User.get_by_url_id(queue.user_id).memberships.filter(by_group=request.group)
                    typepad.client.complete_batch()

                    try:
                        user_membership = user_memberships[0]

                        if user_membership.is_admin():
                            # cannot ban/unban another admin
                            fail.append(item_id)
                            continue

                        user_membership.block()
                        signals.member_banned.send(sender=moderate,
                            membership=user_membership, group=request.group)
                        ban_list.append(queue.user_id)

                    except IndexError:
                        pass # no membership exists; ignore ban

            tp_asset = None

            if queue.asset_id:
                # we need to remove from typepad
                typepad.client.batch_request()
                tp_asset = typepad.Asset.get_by_url_id(queue.asset_id)
                try:
                    typepad.client.complete_batch()
                except typepad.Asset.NotFound:
                    # already deleted on TypePad...
                    tp_asset = None

                if tp_asset:
                    tp_asset.delete()

            content = queue.content
            if content is not None:
                if content.attachment is not None and content.attachment.name:
                    # delete the attachment ourselves; this handles
                    # the case where the file may not actually still be
                    # on disk; we'll just ignore that since we're deleting
                    # the row anyway
                    try:
                        content.attachment.delete()
                    except IOError, ex:
                        # something besides "file couldn't be opened"; reraise
                        if ex.errno != 2:
                            raise ex
                    content.attachment = None
                    content.save()

            queue.delete()
            success.append(item_id)

            if tp_asset is not None:
                signals.asset_deleted.send(sender=moderate, instance=tp_asset, group=request.group)

        elif action == 'view':
            if queue.status in (Queue.MODERATED, Queue.SPAM):
                content = QueueContent.objects.get(queue=queue)
                data = json.loads(content.data)
                # supplement with a fake author member, since this isn't
                # populated into the POSTed data for pre-moderation/spam assets
                data['author'] = {
                    'displayName': queue.user_display_name,
                    'links': [{
                        'rel': 'avatar',
                        'href': queue.user_userpic,
                        'width': 50,
                        'height': 50
                    }]
                }
                tp_asset = typepad.Asset.from_dict(data)
                tp_asset.published = queue.ts
            else:
                typepad.client.batch_request()
                tp_asset = typepad.Asset.get_by_url_id(queue.asset_id)
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

        elif action == 'ban_user':
            typepad.client.batch_request()
            user_memberships = User.get_by_url_id(item_id).memberships.filter(by_group=request.group)
            typepad.client.complete_batch()

            try:
                user_membership = user_memberships[0]

                if user_membership.is_admin():
                    # cannot ban/unban another admin
                    fail.append(item_id)
                    continue

                user_membership.block()
                signals.member_banned.send(sender=moderate,
                    membership=user_membership, group=request.group)
                ban_list.append(item_id)

            except IndexError:
                fail.append(item_id)
                continue

        elif action == 'approve_user':
            user.delete()
            success.append(item_id)

        else:
            return http.HttpResponseForbidden('{"message":"invalid request"}',
                mimetype='application/json')

    if action == 'delete':
        res = 'You deleted %d post(s).' % len(success)
    elif action == 'approve':
        res = 'You approved %d post(s).' % len(success)
    elif action in ('ban', 'ban_user'):
        res = 'You banned %d user(s).' % len(ban_list)
    elif action == 'approve_user':
        res = 'You approved %d user(s).' % len(success)

    data = json.dumps({
        "success": success,
        "fail": fail,
        "message": res
    })
    return http.HttpResponse(data, mimetype='application/json')


signals.asset_deleted.connect(models.clear_local_data_for_asset)
