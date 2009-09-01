var settings = {
    moderate_url: '',
};

// Moderate action
function moderate(id, action) {
    var asset_id = id.split('-')[1]
    $("#loader-" + asset_id).toggle()
    $("#item-" + asset_id).toggle()
    $.ajax({
        type: "POST",
        url: settings.moderate_url,
        data: {"asset_id": asset_id, "action": action},
        success: function(data){
            alert('success: ' + data)
            $("#loader-" + asset_id).toggle()
            // decrement asset count
            var count = parseInt($('#asset-count').html());
            if (isNaN(count))
                count = 0;
            else
                count--;
            $('#asset-count').html(''+count)
        },
        error: function(xhr, txtStatus, errorThrown) {
            alert('An error occurred: ' + xhr.status + ' -- ' + xhr.statusText);
            $("#loader-" + asset_id).toggle()
            $("#item-" + asset_id).toggle()
        }
    });
}

$(document).ready(function () {
    $('.approve').click(function() {
        moderate($(this).attr('id'), 'approve');
        return false;
    });
    $('.delete').click(function() {
        if (confirm('Are you sure you want to delete this post?')) {
            moderate($(this).attr('id'), 'delete');
        }
        return false;
    });
})