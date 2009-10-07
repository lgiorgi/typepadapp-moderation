import simplejson as json
from urlparse import urlparse

from django.db import models
from django.core.urlresolvers import reverse, NoReverseMatch
from django.conf import settings

from oauth import oauth

try:
    settings.USE_MODERATION
except:
    raise Exception('USE_MODERATION setting must be assigned')

try:
    settings.UPLOAD_PATH
except:
    raise Exception('UPLOAD_PATH setting must be assigned')

try:
    settings.REPORT_OPTIONS
except:
    settings.REPORT_OPTIONS = [
        ['Hateful'],
        ['Sexual content'],
        ['Copyright content'],
        ['Spam'],
        ['Admin: Suppress this post immediately', 1]
    ]

import typepad
from typepadapp import models as tp_models


class Asset(models.Model):
    """Summary table for assets that are held or reported.
    """

    # states for these assets
    MODERATED = 1
    FLAGGED = 2
    SUPPRESSED = 3
    APPROVED = 4
    SPAM = 5

    user_id = models.CharField(max_length=35)
    """TypePad user id of the asset owner."""

    user_display_name = models.CharField(max_length=255)
    """The name of the asset owner."""

    user_userpic = models.CharField(max_length=255)
    """The userpic URL of the asset owner."""

    asset_id = models.CharField(max_length=35, null=True)
    """TypePad ID (for flagged assets only)."""

    asset_type = models.CharField(verbose_name="Asset Type", max_length=20,
        db_index=True, default="post")
    """Post type."""

    summary = models.TextField(verbose_name="Summary")
    """Summary of the asset data."""

    ts = models.DateTimeField(auto_now_add=True, db_index=True)
    """Timestamp for the creation of this asset record."""

    status = models.PositiveSmallIntegerField(verbose_name="Status", db_index=True, default=FLAGGED)
    """Status of the asset."""

    flag_count = models.PositiveIntegerField(db_index=True, default=0)
    """Records the total # of reports received for this asset."""

    last_flagged = models.DateTimeField(null=True, db_index=True)
    """Holds the last timestamp we received a report for this asset."""

    def __init__(self, *args, **kwargs):
        super(Asset, self).__init__(*args, **kwargs)
        self._asset = None

    @property
    def content(self):
        try:
            return AssetContent.objects.get(asset=self)
        except:
            return None

    @property
    def asset(self):
        """Returns a TypePad Asset object for this record."""
        content = self.content
        if content is None: return None
        if self._asset is None:
            self._asset = tp_models.Asset.from_dict(json.loads(content.data))
            if self._asset.id is None:
                # this must be a pre-moderated thing; check for a file
                if content.attachment is not None:
                    self._asset.link_relation('enclosure').href = content.attachment.url
        return self._asset

    @property
    def status_class(self):
        try:
            return {
                self.MODERATED:  'moderated',
                self.FLAGGED:    'flagged',
                self.SUPPRESSED: 'suppressed', # flagged, but reached threshold
                self.APPROVED:   'approved',
                self.SPAM:       'spam',
            }[self.status]
        except KeyError:
            return None

    def get_user_url(self):
        """Relative url to the user's member profile page."""
        try:
            return reverse('member', args=[self.user_id])
        except NoReverseMatch:
            return None

    def approve(self):
        if self.status in (Asset.FLAGGED, Asset.SUPPRESSED):
            # clear any flags too while we're at it
            Flag.objects.filter(asset=self).delete()

            # leaving the asset as approved prevents it from being
            # flagged again
            self.flag_count = 0
            self.status = Asset.APPROVED
            self.save()

        elif self.status == Asset.MODERATED:
            content = self.content
            tp_asset = tp_models.Asset.from_dict(json.loads(content.data))

            # setup credentials of post author
            backend = urlparse(settings.BACKEND_URL)
            typepad.client.clear_credentials()
            token = oauth.OAuthToken.from_string(content.user_token)
            oauth_client = tp_models.OAuthClient(tp_models.APPLICATION)
            typepad.client.add_credentials(oauth_client.consumer,
                token, domain=backend[1])

            # TODO: check for fail
            if self.asset_type == 'comment':
                typepad.client.batch_request()
                post = tp_models.Asset.get_by_url_id(tp_asset.in_reply_to.url_id)
                typepad.client.complete_batch()
                post.comments.post(tp_asset)
            else:
                if content.attachment.name:
                    tp_asset.save(group=tp_models.GROUP, file=content.attachment)
                else:
                    tp_asset.save(group=tp_models.GROUP)

            self.delete()


class AssetContent(models.Model):
    """Table to store original post data that will be posted to
    TypePad upon approval."""

    asset = models.OneToOneField(Asset)
    """Reference to parent Asset object."""

    data = models.TextField(blank=False)
    """Holds JSON representation of asset."""

    attachment = models.FileField(upload_to=settings.UPLOAD_PATH)
    """Reference to uploaded file (for upload asset types-- photo and audio)."""

    ip_addr = models.IPAddressField()
    """IP address of user who posted asset."""

    user_token = models.CharField(max_length=255, blank=False)
    """Copy of OAuth token of user who posted asset (for re-posting to TypePad)."""


class Flag(models.Model):
    """Table to record each report we receive.

    This table has a many-to-one relationship with the moderation Asset table."""

    asset = models.ForeignKey(Asset, db_index=True)
    """Reference to parent Asset object."""

    tp_asset_id = models.CharField(max_length=35)
    """TypePad asset ID. 'asset_id' is the reference to the local asset."""

    user_id = models.CharField(max_length=35)
    """TypePad user id of the user reporting this asset."""

    reason_code = models.PositiveSmallIntegerField(default=0)
    """Category code of report."""

    note = models.CharField(max_length=255, blank=True, null=True)
    """A field for a user-supplied note."""

    ts = models.DateTimeField(auto_now_add=True)
    """Timestamp of report."""

    ip_addr = models.IPAddressField()
    """IP address of reporter."""

    @classmethod
    def summary_for_asset(cls, asset):
        rs = cls.objects.filter(asset=asset)
        summary = {}
        for r in rs:
            if r.reason_code in summary:
                summary[r.reason_code] += 1
            else:
                summary[r.reason_code] = 1
        return summary


# we lookup in this table
class Blacklist(models.Model):
    """Table to store user ids we block or moderate for.

    If block is True, the post is blocked; if False, the post is
    moderated."""

    user_id = models.CharField(max_length=35, primary_key=True)
    user_display_name = models.CharField(max_length=255)
    block = models.BooleanField(default=False)
    note = models.CharField(max_length=255, blank=True)


# we lookup in this table
class IPBlock(models.Model):
    """Table to store IP addresses we block or moderate for.

    If block is True, the post is blocked; if False, the post is
    moderated."""

    ip_addr = models.IPAddressField(primary_key=True)
    block = models.BooleanField(default=False)
    note = models.CharField(max_length=255, blank=True)


# we cache in memcache the keyword list from this table; two lists-- one
# for blocks one for moderation
class KeywordBlock(models.Model):
    """Table to store a set of keywords we block or moderate for.
    
    If block is True, the post is blocked outright; if False, the post
    is moderated instead."""

    keyword = models.CharField(max_length=50, unique=True)
    block = models.BooleanField(default=False)
    note = models.CharField(max_length=255, blank=True)
