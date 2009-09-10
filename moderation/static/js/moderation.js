var settings = {
    moderate_url: '',
};

// Moderate action
function moderate(id, action) {
    var asset_id = id.split('-')[1];
    var asset_ids = [];
    if (asset_id == 'checked') {
        $(".item .cb:checked").each(function() {
            asset_id = $(this).val();
            $("#loader-" + asset_id).show();
            $("#item-" + asset_id).hide();
            asset_ids.push(asset_id);
        });
    }
    else {
        $("#loader-" + asset_id).show();
        $("#item-" + asset_id).hide();
        asset_ids = [ asset_id ];
    }
    $.ajax({
        type: "POST",
        url: settings.moderate_url,
        data: { "asset_id": asset_ids, "action": action },
        dataType: "json",
        success: function(data) {
            // hide progress display for rows we've processed
            for (var id in data['success']) {
                $("#loader-" + data['success'][id]).hide();
            }

            // redisplay assets that failed to approve/delete/etc.
            for (var id in data['fail']) {
                $("#loader-" + data['fail'][id]).hide();
                $("#item-" + data['fail'][id]).show();
            }

            // adjust asset count
            var count = parseInt($('#asset-count').html());
            if (isNaN(count))
                count = 0;
            else
                count -= data['success'].length;

            $('#asset-count').html(''+count);
            // show message if no assets left
            if (!count) {
                $('#assets-empty').show();
                $('#assets-footer').show();
            }

            // show flash
            $('#flash-notice').html(data['message']);
            $('#flash-notice').show();
        },
        error: function(xhr, txtStatus, errorThrown) {
            alert('An error occurred: ' + xhr.status + ' -- ' + xhr.statusText);
            for (var id in asset_ids) {
                $("#loader-" + asset_ids[id]).hide();
                $("#item-" + asset_ids[id]).show();
            }
        }
    });
}

function view(id) {
    var asset_id = id.split('-')[1]
    $.ajax({
        type: "POST",
        url: settings.moderate_url,
        data: {"asset_id": asset_id, "action": "view"},
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
        id = $(this).attr('id');
        if (id.indexOf('-checked') >= 0) {
            if (!confirm('Approve the selected items?'))
                return false;
        }
        moderate(id, 'approve');
        return false;
    });

    $('.delete').click(function() {
        id = $(this).attr('id');
        if (id.indexOf('-checked') >= 0) {
            if (!confirm('Delete the selected items?'))
                return false;
        } else if (!confirm('Are you sure you want to delete this post?')) {
            return false;
        }
        moderate($(this).attr('id'), 'delete');
        return false;
    });

    $('.ban').click(function() {
        id = $(this).attr('id');
        if (id.indexOf('-checked') >= 0) {
            if (!confirm('Ban users who posted these items (also deletes selected posts)?'))
                return false;
        } else if (!confirm('Are you sure you want to ban this user (also deletes this post)?')) {
            return false;
        }
        moderate(id, 'ban');
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
