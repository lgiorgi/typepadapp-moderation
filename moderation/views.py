from typepadapp.views.base import TypePadView
from moderation.models import Asset


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