from typepadapp.views.base import TypePadView


class ModerationView(TypePadView):
    """
    Moderation home page.
    """
    template_name = "moderation/index.html"