# Copyright (c) 2009-2010 Six Apart Ltd.
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

import re

from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user
from django.conf import settings

import typepad
from typepadapp.views.base import TypePadView
from moderation.models import Queue, Approved, Flag, QueueContent, Blacklist, IPBlock, user_can_post
from typepadapp.decorators import ajax_required

import simplejson as json
from datetime import datetime

try:
    import akismet
except:
    akismet = None

ITEMS_PER_PAGE = 18 # TODO move this to settings!


class DashboardView(TypePadView):
    """
    Moderation home page.
    """

    admin_required = True
    template_name = "moderation/dashboard.html"

    def get(self, request, *args, **kwargs):
        total_pending = Queue.objects.filter(status=Queue.MODERATED).count()
        total_flagged = Queue.objects.filter(status__in=[Queue.FLAGGED,
            Queue.SUPPRESSED]).count()
        total_spam = Queue.objects.filter(status=Queue.SPAM).count()
        self.context.update(locals())
        return super(DashboardView, self).get(request, *args, **kwargs)


class PendingView(TypePadView):
    """
    Moderation queue of every new post, pending approval.
    """

    admin_required = True
    template_name = "moderation/pending.html"
    paginate_by = ITEMS_PER_PAGE

    def select_from_typepad(self, request, view='moderation_pending',
        *args, **kwargs):
        self.paginate_template = reverse('moderation_pending') + '/page/%d'
        self.object_list = Queue.objects.filter(status=Queue.MODERATED).order_by('ts')

    def get(self, request, *args, **kwargs):
        # Limit the number of objects to display since the FinitePaginator doesn't do this
        assets = self.object_list[self.offset-1:self.offset-1+self.limit]
        self.context.update(locals())
        return super(PendingView, self).get(request, *args, **kwargs)


class SpamView(TypePadView):
    """
    Moderation queue of spam posts.
    """

    admin_required = True
    template_name = "moderation/spam.html"
    paginate_by = ITEMS_PER_PAGE

    def select_from_typepad(self, request, view='moderation_spam', *args, **kwargs):
        self.paginate_template = reverse('moderation_spam') + '/page/%d'
        self.object_list = Queue.objects.filter(status=Queue.SPAM).order_by('ts')

    def get(self, request, *args, **kwargs):
        # Limit the number of objects to display since the FinitePaginator doesn't do this
        assets = self.object_list[self.offset-1:self.offset-1+self.limit]
        self.context.update(locals())
        return super(SpamView, self).get(request, *args, **kwargs)


class FlaggedView(TypePadView):
    """
    Moderation home page.
    """

    admin_required = True
    template_name = "moderation/flagged.html"
    paginate_by = ITEMS_PER_PAGE

    def select_from_typepad(self, request, view='moderation_flagged',
        *args, **kwargs):
        self.paginate_template = reverse('moderation_flagged') + '/page/%d'
        if request.GET.get('sort', None) == 'latest':
            self.paginate_template += '?sort=latest'
            self.object_list = Queue.objects.filter(status__in=[Queue.FLAGGED,
                Queue.SUPPRESSED]).order_by('last_flagged', '-flag_count')
        else:
            self.object_list = Queue.objects.filter(status__in=[Queue.FLAGGED,
                Queue.SUPPRESSED]).order_by('-flag_count', 'last_flagged')

    def get(self, request, *args, **kwargs):
        # Limit the number of objects to display since the FinitePaginator
        # doesn't do this
        assets = self.object_list[self.offset-1:self.offset-1+self.limit]
        self.context.update(locals())
        return super(FlaggedView, self).get(request, *args, **kwargs)


class FlaggedFlagsView(TypePadView):
    """
    Show who has flagged a particular post and why.
    """

    admin_required = True
    template_name = "moderation/flags.html"
    paginate_by = ITEMS_PER_PAGE

    def select_from_typepad(self, request, view='moderation_flagged_flags',
        *args, **kwargs):
        self.queue = Queue.objects.get(asset_id=kwargs['assetid'])
        self.object_list = Flag.objects.filter(queue=self.queue)

    def get(self, request, *args, **kwargs):
        # Limit the number of objects to display since the FinitePaginator
        # doesn't do this
        flags = self.object_list[self.offset-1:self.offset-1+self.limit]
        asset = self.queue
        self.context.update(locals())
        return super(FlaggedFlagsView, self).get(request, *args, **kwargs)


def moderation_report(request):
    asset_id = request.POST['asset-id']
    reason_code = int(request.POST.get('reason', 0))
    note = request.POST.get('note', None)
    return_to = request.POST.get('return_to', reverse('home'))
    return_to = re.sub('.*?/', '/', return_to)

    ip = request.META['REMOTE_ADDR']

    typepad.client.batch_request()
    user = get_user(request)
    asset = typepad.Asset.get_by_url_id(asset_id)
    try:
        typepad.client.complete_batch()
    except typepad.Asset.NotFound:
        if request.is_ajax():
            return HttpResponse(_("The requested post was not found."), mimetype='text/plain')
        else:
            return HttpResponse('ERROR', mimetype='text/plain')

    # TODO: Should we behave differently if the user is an admin?

    queue = Queue.objects.filter(asset_id=asset_id)
    if not queue:
        queue = Queue()
        queue.asset_id = asset_id
        queue.summary = unicode(asset)
        queue.asset_type = asset.type_id
        queue.user_id = asset.user.url_id
        queue.user_display_name = asset.user.display_name
        queue.user_userpic = asset.user.userpic
        queue.flag_count = 1
        queue.status = Queue.FLAGGED
        queue.last_flagged = datetime.now()
    else:
        queue = queue[0]
        queue.flag_count += 1

    approved = Approved.objects.filter(asset_id=asset_id)

    if len(approved):
        if request.is_ajax():
            return HttpResponse(_("This post has been approved by the site moderator."), mimetype='text/plain')
        else:
            request.flash.add('notices', _('This post has been approved by the site moderator.'))
            return HttpResponseRedirect(return_to)


    # determine if this report is going to suppress the asset or not.
    if queue.status != Queue.SUPPRESSED:
        # count # of flags for this reason and asset:
        if len(settings.REPORT_OPTIONS[reason_code]) > 1:
            trigger = settings.REPORT_OPTIONS[reason_code][1]
            count = Flag.objects.filter(tp_asset_id=asset_id, reason_code=reason_code).count()
            if count + 1 >= trigger:
                queue.status = Queue.SUPPRESSED


    queue.save()

    # to avoid having to hit typepad for viewing this content,
    # save a local copy to make moderation as fast as possible
    # this data is removed once the post is processed.
    if not queue.content:
        content = QueueContent()
        content.data = json.dumps(asset.to_dict())
        content.queue = queue
        content.user_token = 'none'
        content.ip_addr = '0.0.0.0'
        content.save()


    flag = Flag.objects.filter(user_id=user.url_id, queue=queue)
    if not flag:
        # lets not allow a single user to repeat a report on the same asset
        flag = Flag()
        flag.queue = queue
        flag.tp_asset_id = asset_id
        flag.user_id = user.url_id
        flag.user_display_name = user.display_name
        if reason_code is not None:
            flag.reason_code = reason_code
        if note is not None:
            flag.note = note
        flag.ip_addr = ip
        flag.save()
    else:
        flag = flag[0]
        if reason_code and flag.reason_code != reason_code:
            flag.reason_code = reason_code
            flag.ip_addr = ip
            if note is not None:
                flag.note = note
            flag.save()

    if request.is_ajax():
        return HttpResponse('OK', mimetype='text/plain')
    else:
        request.flash.add('notices', _('Thank you for your report.'))
        if queue.status == Queue.SUPPRESSED:
            return HttpResponseRedirect(reverse('home'))
        else:
            return HttpResponseRedirect(return_to)


def browser_upload(request):
    if not hasattr(request, 'user'):
        typepad.client.batch_request()
        user = get_user(request)
        typepad.client.complete_batch()

        request.user = user

    if not request.method == 'POST':
        status = moderation_status(request)

        if status == Queue.APPROVED:
            import motion.ajax
            return motion.ajax.upload_url(request)

        url = reverse('moderated_upload_url')
        url = 'for(;;);%s' % url # no third party sites allowed.
        return HttpResponse(url)

    if not request.user.is_authenticated():
        return HttpResponseForbidden("invalid request")

    data = json.loads(request.POST['asset'])
    tp_asset = typepad.Asset.from_dict(data)

    moderate_post(request, tp_asset)

    return HttpResponseRedirect(reverse('home'))


def moderate_post(request, post):
    """Determines the moderation behavior for the request and asset posted.

    Returns True when the post has been handled (pre-moderated or blocked),
    and returns False when the post is approved for posting."""
    # save a copy of this content to our database

    # do this check first of all to avoid any possible spam filtering
    if request.user.is_superuser or request.user.is_featured_member:
        return False

    post_status = moderation_status(request, post)

    if post_status is None:
        # blocked; don't post to typepad
        return True

    if is_spam(request, post):
        # spammy posts get pre-moderated
        post_status = Queue.SPAM

    # if moderation_status says the asset can be published, let it be so
    # what to do about uploads though?
    if post_status == Queue.APPROVED:
        return False

    queue = Queue()
    queue.asset_type = post.type_id
    queue.user_id = request.user.url_id
    queue.user_display_name = request.user.display_name
    queue.user_userpic = request.user.userpic
    queue.summary = unicode(post)
    queue.status = post_status
    queue.save()

    content = QueueContent()
    content.queue = queue
    content.data = json.dumps(post.to_dict())
    if request.FILES:
        content.attachment = request.FILES['file']
    content.user_token = request.oauth_client.token.to_string()
    content.ip_addr = request.META['REMOTE_ADDR']
    content.save()

    request.flash.add('notices', _('Thank you. Your post is awaiting moderation by the Administrator.'))

    return True


def moderation_status(request, post=None):
    """Returns a status for the post; None if the post is not permitted at all.

    This routine can be called without a post to attempt to determine the
    moderation status of the user in context (whether they are blocked or not)."""

    # don't moderate admins or featured users. ever.
    if request.user.is_superuser or request.user.is_featured_member:
        return Queue.APPROVED

    moderate_everything = True

    user_moderation = False
    if hasattr(settings, 'MODERATE_BY_USER') and settings.MODERATE_BY_USER:
        user_moderation = True
        moderate_everything = False

    type_moderation = False
    post_type = (post and post.type_id) or request.GET.get('post_type')
    if hasattr(settings, 'MODERATE_TYPES'):
        if (settings.MODERATE_TYPES is not None) and \
            len(settings.MODERATE_TYPES) > 0:
            type_moderation = True
        moderate_everything = False

    # if neither MODERATE_BY_USER or MODERATE_TYPES is specified, we presume to
    # moderate everything
    if moderate_everything:
        return Queue.MODERATED

    # OK, we are NOT moderating everything; so now we have to prove moderation
    # by testing if this post type and/or user is moderated
    moderate = False

    # check for user/ip blocks
    if user_moderation:
        can_post, moderate = user_can_post(request.user, request.META['REMOTE_ADDR'])
        if not can_post:
            if not request.is_ajax():
                request.flash.add('notices', _('Sorry; you are not allowed to post to this site.'))
            # we can't allow this user, so no post status
            return None

    if type_moderation and (post_type is not None) and not moderate:
        # if this setting is available, only moderate for specified types;
        # otherwise, moderate everything
        moderate = post_type in settings.MODERATE_TYPES

    return (moderate and Queue.MODERATED) or Queue.APPROVED


def is_spam(request, post):
    """Sends post content to TypePad AntiSpam for spam check.

    Returns True if TPAS determines it is spam, False if not."""

    # if we don't have akismet, we don't know; assume it isn't spam
    if not akismet:
        return False

    # they didn't bother configuring an api key, so we can't test for spam
    if not hasattr(settings, 'TYPEPAD_ANTISPAM_API_KEY'):
        return False

    ak = akismet.Akismet(
        key=settings.TYPEPAD_ANTISPAM_API_KEY,
        blog_url=settings.FRONTEND_URL
    )
    ak.baseurl = 'api.antispam.typepad.com/1.1/'

    if ak.verify_key():
        data = {
            'user_ip': request.META.get('REMOTE_ADDR', '127.0.0.1'),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'referrer': request.META.get('HTTP_REFERER', ''),
            'comment_type': 'comment',
            'comment_author': request.user.display_name.encode('utf-8'),
        }

        content = post.content

        # for link assets, lets include the link too
        if isinstance(post, typepad.LinkAsset):
            content += "\n" + post.target_url

        # TPAS seems to rate empty posts as spam; since some asset types
        # permit empty content (photo, audio, video posts for instance,
        # we should allow these to pass)
        encoded = content.encode('utf-8')
        if encoded != '':
            if ak.comment_check(encoded, data=data, build_data=True):
                return True

    return False
