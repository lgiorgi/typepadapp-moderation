from typepadapp.views.base import TypePadView


class DashboardView(TypePadView):
    """
    Moderation home page.
    """

    admin_required = True

    template_name = "moderation/dashboard.html"


class PendingView(TypePadView):
    """
    Moderation home page.
    """

    admin_required = True

    template_name = "moderation/pending.html"


class FlaggedView(TypePadView):
    """
    Moderation home page.
    """

    admin_required = True

    template_name = "moderation/flagged.html"