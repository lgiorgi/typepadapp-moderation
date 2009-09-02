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


class DashboardView(TypePadView):
    """
    Moderation home page.
    """

    admin_required = True

    template_name = "moderation/dashboard.html"


class PendingView(TypePadView):
    """
    Moderation queue of every new post, pending approval.
    """

    template_name = "moderation/pending.html"
    admin_required = True

    def select_from_typepad(self, request, view='moderation_pending', *args, **kwargs):
        assets = Asset.objects.filter(status=Asset.MODERATED)
        self.context.update(locals())


class FlaggedView(TypePadView):
    """
    Moderation home page.
    """

    admin_required = True

    template_name = "moderation/flagged.html"

    def select_from_typepad(self, request, view='moderation_pending', *args, **kwargs):
        assets = Asset.objects.filter(status__in=[Asset.FLAGGED, Asset.SUPPRESSED])
        self.context.update(locals())


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

    flag = Flag.objects.filter(user_id=user.url_id, asset=local_asset)
    if not flag:
        # lets not allow a single user to repeat a report on the same asset
        flag = Flag()
        flag.asset = local_asset
        flag.tp_asset_id = asset_id
        flag.user_id = user.url_id
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
    if not request.method == 'POST':
        url = reverse('upload_url')
        url = 'for(;;);%s' % url # no third party sites allowed.
        return HttpResponse(url)

    typepad.client.batch_request()
    user = get_user(request)
    typepad.client.complete_batch()

    if not user.is_authenticated():
        return HttpResponseForbidden("invalid request")

    ip = request.META['REMOTE_ADDR']


    # check for user/ip blocks
    blacklisted = Blacklist.objects.filter(user_id=user.url_id)
    ipblocked = IPBlock.objects.filter(ip_addr=ip)

    if (blacklisted and blacklisted.block) \
        or (ipblocked and ipblocked.block):
        return HttpResponseForbidden("Sorry, you are not allowed to post.")


    if request.FILES:
        data = json.loads(request.POST['asset'])
        tp_asset = typepad.Asset.from_dict(data)
    else:
        # some server-side validation
        # non-file post
        from motion import forms
        form = forms.PostForm(request.POST, request.FILES)

        if form.is_valid():
            tp_asset = form.save()
        else:
            request.flash.add('errors', _('Please correct the errors below.'))
            return HttpResponseRedirect(request.path)


    # save a copy of this content to our database

    asset = Asset()
    asset.asset_type = tp_asset.type_id
    asset.user_id = user.url_id
    asset.user_display_name = user.display_name
    asset.summary = unicode(tp_asset)
    asset.status = Asset.MODERATED
    asset.save()

    content = AssetContent()
    content.asset = asset
    content.data = json.dumps(tp_asset.to_dict())
    if request.FILES:
        content.attachment = request.FILES['file']
    content.user_token = request.oauth_client.token.to_string()
    content.ip_addr = ip
    content.save()

    request.flash.add('notices', _('Thank you for your submission. It is awaiting moderation.'))
    return HttpResponseRedirect(reverse('home'))
