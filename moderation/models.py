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

import simplejson as json
from urlparse import urlparse

from django.db import models
from django.core.urlresolvers import reverse, NoReverseMatch
from django.conf import settings

from typepadapp import signals

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


class Approved(models.Model):
    "A holding table for all approved assets."

    asset_id = models.CharField(max_length=35, primary_key=True)


class Queue(models.Model):
    """Summary table for assets that are held or reported.
    """

    # states for these assets
    APPROVED = 0
    MODERATED = 1
    FLAGGED = 2
    SUPPRESSED = 3
    SPAM = 4

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
        super(Queue, self).__init__(*args, **kwargs)
        self._asset = None

    @property
    def content(self):
        try:
            return QueueContent.objects.get(queue=self)
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
                if content.attachment is not None and content.attachment.name:
                    self._asset.link_relation('enclosure').href = content.attachment.url
        return self._asset

    @property
    def status_class(self):
        try:
            return {
                self.MODERATED:  'moderated',
                self.FLAGGED:    'flagged',
                self.SUPPRESSED: 'suppressed', # flagged, but reached threshold
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
        if self.status in (Queue.FLAGGED, Queue.SUPPRESSED):
            # clear any flags too while we're at it
            Flag.objects.filter(queue=self).delete()
            self.delete()

            approved = Approved()
            approved.asset_id = self.asset_id
            approved.save()

        elif self.status in (Queue.MODERATED, Queue.SPAM):
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
                signals.asset_created.send(sender=self.approve, instance=tp_asset, group=tp_models.GROUP, parent=post)
            else:
                if content.attachment.name:
                    tp_asset.save(group=tp_models.GROUP, file=content.attachment)
                else:
                    tp_asset.save(group=tp_models.GROUP)
                signals.asset_created.send(sender=self.approve, instance=tp_asset, group=tp_models.GROUP)

            self.delete()


class QueueContent(models.Model):
    """Table to store original post data that will be posted to
    TypePad upon approval."""

    queue = models.OneToOneField(Queue)
    """Reference to parent Queue object."""

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

    This table has a many-to-one relationship with the moderation Queue table."""

    queue = models.ForeignKey(Queue, db_index=True)
    """Reference to parent Queue object."""

    tp_asset_id = models.CharField(max_length=35)
    """TypePad asset ID. 'asset_id' is the reference to the local asset."""

    user_id = models.CharField(max_length=35)
    """TypePad user id of the user reporting this asset."""

    user_display_name = models.CharField(max_length=255)
    """Name of the user reporting this asset."""

    reason_code = models.PositiveSmallIntegerField(default=0)
    """Category code of report."""

    note = models.CharField(max_length=255, blank=True, null=True)
    """A field for a user-supplied note."""

    ts = models.DateTimeField(auto_now_add=True)
    """Timestamp of report."""

    ip_addr = models.IPAddressField()
    """IP address of reporter."""

    def reason(self):
        # TODO catch IndexError?
        return settings.REPORT_OPTIONS[self.reason_code][0]

    def get_user_url(self):
        """Relative url to the user's member profile page."""
        try:
            return reverse('member', args=[self.user_id])
        except NoReverseMatch:
            return None

    @classmethod
    def summary_for_asset(cls, asset):
        rs = cls.objects.filter(queue=asset)
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


def user_can_post(user, ip_addr):
    """Returns a tuple identifying the posting state of the user in
    the eyes of the moderation app.

    The first value is a boolean as to whether the user is allowed
    to create posts. The second identifies the moderation status."""

    blacklisted = Blacklist.objects.filter(user_id=user.url_id)
    if blacklisted:
        if blacklisted[0].block:
            return False, False
        else:
            return True, True

    ipblocked = IPBlock.objects.filter(ip_addr=ip_addr)
    if ipblocked:
        if ipblocked[0].block:
            return False, False
        else:
            return True, True

    return True, False

def clear_local_data_for_asset(sender, instance=None, **kwargs):
    """Django signal handler for deleting all local records referring to the
    TypePad asset passed as the ``instance`` keyword argument."""

    if instance is None: return

    asset_id = instance.url_id
    Approved.objects.filter(asset_id=asset_id).delete()
    Queue.objects.filter(asset_id=asset_id).delete()
    Flag.objects.filter(tp_asset_id=asset_id).delete()
