/*
 * Copyright (c) 2009-2010 Six Apart Ltd.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * * Redistributions of source code must retain the above copyright notice,
 *   this list of conditions and the following disclaimer.
 *
 * * Redistributions in binary form must reproduce the above copyright notice,
 *   this list of conditions and the following disclaimer in the documentation
 *   and/or other materials provided with the distribution.
 *
 * * Neither the name of Six Apart Ltd. nor the names of its contributors may
 *   be used to endorse or promote products derived from this software without
 *   specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

var settings = {
    moderate_url: ''
};

function toggleDetail(id) {
    id = '#' + id;
    if ($(id).hasClass("closed"))
        $(id).removeClass("closed").addClass("open");
    else
        $(id).removeClass("open").addClass("closed");
    return false;
}

// Moderate action
function moderate(id, action, redirect) {
    var item_id = id.split('-')[1];
    var item_ids = [];
    if (item_id == 'checked') {
        $(".item .cb:checked").each(function() {
            item_id = $(this).val();
            $("#loader-" + item_id).show();
            $("#item-" + item_id).hide();
            item_ids.push(item_id);
        });
    }
    else {
        $("#loader-" + item_id).show();
        $("#item-" + item_id).hide();
        item_ids = [ item_id ];
    }
    $.ajax({
        type: "POST",
        url: settings.moderate_url,
        data: { "item_id": item_ids, "action": action },
        dataType: "json",
        success: function(data) {
            if (redirect) {
                window.location = redirect;
            } else {
                // hide progress display for rows we've processed
                for (var id in data['success']) {
                    $("#loader-" + data['success'][id]).hide();
                    $("#item-" + data['success'][id] + ' .cb[type="checkbox"]').attr('checked', false);
                }
                // redisplay items that failed to approve/delete/etc.
                for (var id in data['fail']) {
                    $("#loader-" + data['fail'][id]).hide();
                    $("#item-" + data['fail'][id]).show();
                }
                // adjust item count
                var count = parseInt($('#item-count').html());
                if (isNaN(count))
                    count = 0;
                else {
                    count -= data['success'].length;
                    if (count < 0) count = 0;
                }
                $('#item-count').html(''+count);
                // show message if no assets left
                if (!count) {
                    $('#items-empty').show();
                    $('#items-footer').show();
                }
                // show flash
                $('#flash-notice').html(data['message']);
                $('#flash-notice').show();
            }
        },
        error: function(xhr, txtStatus, errorThrown) {
            alert('An error occurred: ' + xhr.status + ' -- ' + xhr.statusText);
            for (var id in item_ids) {
                $("#loader-" + item_ids[id]).hide();
                $("#item-" + item_ids[id]).show();
            }
        }
    });
}

function view(id) {
    var asset_id = id.split('-')[1]
    $.ajax({
        type: "POST",
        url: settings.moderate_url,
        data: {"item_id": asset_id, "action": "view"},
        success: function(data){
            // decrement asset count
            $('#view-detail').html(data);
            $('#view-dialog').dialog('open');
        },
        error: function(xhr, txtStatus, errorThrown) {
            alert('An error occurred: ' + xhr.status + ' -- ' + xhr.statusText);
        }
    });
}

$(document).ready(function () {
    $('.approve').click(function() {
        var id = $(this).attr('id');
        if (id.indexOf('-checked') >= 0) {
            if (!confirm('Approve the selected items?'))
                return false;
        }
        moderate(id, 'approve', $(this).attr('href'));
        return false;
    });

    $('.delete').click(function() {
        var id = $(this).attr('id');
        if (id.indexOf('-checked') >= 0) {
            if (!confirm('Delete the selected items?'))
                return false;
        } else if (!confirm('Are you sure you want to delete this post?')) {
            return false;
        }
        moderate(id, 'delete', $(this).attr('href'));
        return false;
    });

    $('.ban').click(function() {
        var id = $(this).attr('id');
        if (id.indexOf('-checked') >= 0) {
            if (!confirm('Ban users who posted these items (also deletes selected posts)?'))
                return false;
        } else if (!confirm('Are you sure you want to ban this user (also deletes this post)?')) {
            return false;
        }
        moderate(id, 'ban', $(this).attr('href'));
        return false;
    });

    $('.ban-user').click(function() {
        var id = $(this).attr('id');
        if (id.indexOf('-checked') >= 0) {
            if (!confirm('Ban selected users (does not affect posts already made to the group)?'))
                return false;
        } else if (!confirm('Are you sure you want to ban this user (does not affect posts already made to the group)?')) {
            return false;
        }
        moderate(id, 'ban_user', $(this).attr('href'));
        return false;
    });

    $('.approve-user').click(function() {
        var id = $(this).attr('id');
        if (id.indexOf('-checked') >= 0) {
            if (!confirm('Approve the selected users?'))
                return false;
        }
        moderate(id, 'approve_user', $(this).attr('href'));
        return false;
    });

    $('.view').click(function() {
        if (!$(this).attr('id')) return true;
        view($(this).attr('id'), 'view');
        return false;
    });

    $('.check-all').click(function() {
        $('.item .cb[type="checkbox"]').attr('checked', $(this).attr('checked') ? 'checked': false);
    });
})
