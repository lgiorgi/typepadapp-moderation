from typepadapp.views.base import TypePadView


class ModerationView(TypePadView):
    """
    Moderation home page.
    """

    admin_required = True

    template_name = "moderation/index.html"
