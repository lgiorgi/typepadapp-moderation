from django.db import models
from django.conf import settings


assert(settings.UPLOAD_PATH)


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

    asset_id = models.CharField(max_length=35, unique=True)
    """TypePad ID (for flagged assets only)."""

    asset_type = models.CharField(verbose_name="Asset Type", max_length=20,
        db_index=True, default="post")
    """Post type."""

    summary = models.TextField(verbose_name="Summary")
    """Summary of the asset data."""

    ts = models.DateTimeField(auto_now_add=True)
    """Timestamp for the creation of this asset record."""

    status = models.PositiveSmallIntegerField(verbose_name="Status", db_index=True, default=FLAGGED)
    """Status of the asset."""

    flag_count = models.PositiveIntegerField(db_index=True, default=0)
    """Records the total # of reports received for this asset."""

    last_flagged = models.DateTimeField(null=True)
    """Holds the last timestamp we received a report for this asset."""

    @property
    def status_class(self):
        try:
            return {
                MODERATED:  'moderated',
                FLAGGED:    'flagged',
                SUPPRESSED: 'suppressed', # flagged, but reached threshold
                APPROVED:   'approved',
                SPAM:       'spam',
            }[self.status]
        except KeyError:
            return None


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

    user_token = models.CharField(max_length=50, blank=False)
    """Copy of OAuth token of user who posted asset (for re-posting to TypePad)."""


class Flag(models.Model):
    """Table to record each report we receive.

    This table has a many-to-one relationship with the moderation Asset table."""

    asset = models.ForeignKey(Asset, db_index=True)
    """Reference to parent Asset object."""

    user_id = models.CharField(max_length=35)
    """TypePad user id of the user reporting this asset."""

    reason_code = models.PositiveSmallIntegerField()
    """Category code of report."""

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
