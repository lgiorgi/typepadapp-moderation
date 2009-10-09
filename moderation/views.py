from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user
from django.conf import settings

import typepad
from typepadapp.views.base import TypePadView
from moderation.models import Asset, Flag, AssetContent, Blacklist, IPBlock
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
        total_pending = Asset.objects.filter(status=Asset.MODERATED).count()
        total_flagged = Asset.objects.filter(status__in=[Asset.FLAGGED, Asset.SUPPRESSED]).count()
        total_spam = Asset.objects.filter(status=Asset.SPAM).count()
        self.context.update(locals())
        return super(DashboardView, self).get(request, *args, **kwargs)


class PendingView(TypePadView):
    """
    Moderation queue of every new post, pending approval.
    """

    admin_required = True
    template_name = "moderation/pending.html"
    paginate_by = ITEMS_PER_PAGE

    def select_from_typepad(self, request, view='moderation_pending', *args, **kwargs):
        self.paginate_template = reverse('pending') + '/page/%d'
        self.object_list = Asset.objects.filter(status=Asset.MODERATED).order_by('ts')

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
        self.paginate_template = reverse('spam') + '/page/%d'
        self.object_list = Asset.objects.filter(status=Asset.SPAM).order_by('ts')

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

    def select_from_typepad(self, request, view='moderation_flagged', *args, **kwargs):
        self.paginate_template = reverse('flagged') + '/page/%d'
        if request.GET.get('sort', None) == 'latest':
            self.object_list = Asset.objects.filter(status__in=[Asset.FLAGGED, Asset.SUPPRESSED]).order_by('last_flagged', '-flag_count')
        else:
            self.object_list = Asset.objects.filter(status__in=[Asset.FLAGGED, Asset.SUPPRESSED]).order_by('-flag_count', 'last_flagged')

    def get(self, request, *args, **kwargs):
        # Limit the number of objects to display since the FinitePaginator doesn't do this
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

    def select_from_typepad(self, request, view='moderation_flagged_flags', *args, **kwargs):
        self.asset = Asset.objects.get(asset_id=kwargs['assetid'])
        self.object_list = Flag.objects.filter(asset=self.asset)

    def get(self, request, *args, **kwargs):
        # Limit the number of objects to display since the FinitePaginator doesn't do this
        flags = self.object_list[self.offset-1:self.offset-1+self.limit]
        asset = self.asset
        self.context.update(locals())
        return super(FlaggedFlagsView, self).get(request, *args, **kwargs)


def moderation_report(request):
    asset_id = request.POST['asset-id']
    reason_code = int(request.POST.get('reason', 0))
    note = request.POST.get('note', None)

    ip = request.META['REMOTE_ADDR']

    # TBD: verify asset_id looks like an xid

    typepad.client.batch_request()
    user = get_user(request)
    asset = typepad.Asset.get_by_url_id(asset_id)
    try:
        typepad.client.complete_batch()
    except:
        return HttpResponse('ERROR', mimetype='text/plain')

    # TODO: Should we behave differently if the user is an admin?

    local_asset = Asset.objects.filter(asset_id=asset_id)
    if not local_asset:
        local_asset = Asset()
        local_asset.asset_id = asset_id
        local_asset.summary = unicode(asset)
        local_asset.asset_type = asset.type_id
        local_asset.user_id = asset.user.url_id
        local_asset.user_display_name = asset.user.display_name
        local_asset.user_userpic = asset.user.userpic
        local_asset.flag_count = 1
        local_asset.status = Asset.FLAGGED
        local_asset.last_flagged = datetime.now()
    else:
        local_asset = local_asset[0]
        local_asset.flag_count += 1


    if local_asset.status == Asset.APPROVED:
        request.flash.add('notices', _('This post has been approved by the site moderator.'))
        return HttpResponseRedirect(asset.get_absolute_url())


    # determine if this report is going to suppress the asset or not.
    if local_asset.status != Asset.SUPPRESSED:
        # count # of flags for this reason and asset:
        if len(settings.REPORT_OPTIONS[reason_code]) > 1:
            trigger = settings.REPORT_OPTIONS[reason_code][1]
            count = Flag.objects.filter(tp_asset_id=asset_id, reason_code=reason_code).count()
            if count + 1 >= trigger:
                local_asset.status = Asset.SUPPRESSED


    local_asset.save()

    # to avoid having to hit typepad for viewing this content,
    # save a local copy to make moderation as fast as possible
    # this data is removed once the post is processed.
    if not local_asset.content:
        content = AssetContent()
        content.data = json.dumps(asset.to_dict())
        content.asset = local_asset
        content.user_token = 'none'
        content.ip_addr = '0.0.0.0'
        content.save()


    flag = Flag.objects.filter(user_id=user.url_id, asset=local_asset)
    if not flag:
        # lets not allow a single user to repeat a report on the same asset
        flag = Flag()
        flag.asset = local_asset
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
        return HttpRepsonse('OK', mimetype='text/plain')
    else:
        request.flash.add('notices', _('Thank you for your report.'))
        return HttpResponseRedirect(asset.get_absolute_url())


def browser_upload(request):
    if not hasattr(request, 'user'):
        typepad.client.batch_request()
        user = get_user(request)
        typepad.client.complete_batch()

        request.user = user

    if not request.method == 'POST':
        status = moderation_status(request)

        if status == Asset.APPROVED:
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

    post_status = moderation_status(request, post)

    if post_status is None:
        # blocked; don't post to typepad
        return True

    if is_spam(request, post):
        # spammy posts get pre-moderated
        post_status = Asset.SPAM

    # if moderation_status says the asset can be published, let it be so
    # what to do about uploads though?
    if post_status == Asset.APPROVED:
        return False

    asset = Asset()
    asset.asset_type = post.type_id
    asset.user_id = request.user.url_id
    asset.user_display_name = request.user.display_name
    asset.user_userpic = request.user.userpic
    asset.summary = unicode(post)
    asset.status = post_status
    asset.save()

    content = AssetContent()
    content.asset = asset
    content.data = json.dumps(post.to_dict())
    if request.FILES:
        content.attachment = request.FILES['file']
    content.user_token = request.oauth_client.token.to_string()
    content.ip_addr = request.META['REMOTE_ADDR']
    content.save()

    request.flash.add('notices', _('Thank you for your submission. It is awaiting moderation.'))

    return True


def moderation_status(request, post=None):
    """Returns True if the request passes the filter, False if the request
    cannot continue."""

    # don't moderate admins or featured users
    if request.user.is_superuser or request.user.is_featured_member:
        return Asset.APPROVED

    # default assumption for USE_MODERATION is to moderate all;
    # if MODERATE_SOME is True, use selective moderation
    if not hasattr(settings, 'MODERATE_SOME') \
        or not settings.MODERATE_SOME:
        # we moderate everything
        return Asset.MODERATED

    # check for user/ip blocks
    blacklisted = Blacklist.objects.filter(user_id=request.user.url_id)
    ipblocked = IPBlock.objects.filter(ip_addr=request.META['REMOTE_ADDR'])

    if not (blacklisted or ipblocked):
        return Asset.APPROVED

    if (blacklisted and blacklisted[0].block) \
        or (ipblocked and ipblocked[0].block):
        if not request.is_ajax():
            request.flash.add('notices', _('Sorry; you are not allowed to post to this site.'))
        # we can't allow this user, so no post status
        return None

    if post is not None:
        # if this setting is available, only moderate for specified types;
        # otherwise, moderate everything
        if hasattr(settings, 'MODERATE_TYPES'):
            if not post.type_id in settings.MODERATE_TYPES:
                return Asset.APPROVED

    return Asset.MODERATED


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
            content += "\n" + post.links['target'].href

        # TPAS seems to rate empty posts as spam; since some asset types
        # permit empty content (photo, audio, video posts for instance,
        # we should allow these to pass)
        if str(content) != '':
            if ak.comment_check(content.encode('utf-8'), data=data, build_data=True):
                return True

    return False
