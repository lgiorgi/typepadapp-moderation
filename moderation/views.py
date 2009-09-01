from django.http import HttpResponse, HttpResponseRedirect
from django.utils.translation import ugettext as _

import typepad
from typepadapp.views.base import TypePadView
from moderation.models import Asset, Flag
from typepadapp.decorators import ajax_required

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
        assets = Asset.objects.filter(status=1)
        self.context.update(locals())


class FlaggedView(TypePadView):
    """
    Moderation home page.
    """

    admin_required = True

    template_name = "moderation/flagged.html"


def moderation_report(request):
    from django.contrib.auth import get_user

    asset_id = request.POST['asset-id']
    reason_code = request.POST.get('reason', None)

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
        local_asset.flag_count = 1
        local_asset.status = Asset.FLAGGED
        local_asset.last_flagged = datetime.now()
    else:
        local_asset = local_asset[0]
        local_asset.flag_count += 1

    flag = Flag.objects.filter(user_id=request.user.url_id, asset=local_asset)
    if not flag:
        # lets not allow a single user to repeat a report on the same asset
        flag = Flag()
        flag.asset = local_asset
        flag.user_id = request.user.url_id
        if reason_code is not None:
            flag.reason_code = reason_code
        flag.ip_addr = ip
        flag.save()
        local_asset.save()
    else:
        flag = flag[0]
        if reason_code and flag.reason_code != reason_code:
            flag.reason_code = reason_code
            flag.ip_addr = ip
            flag.save()

    if request.is_ajax():
        return HttpRepsonse('OK', mimetype='text/plain')
    else:
        request.flash.add('notices', _('Thank you for your report.'))
        return HttpResponseRedirect(asset.get_absolute_url())
