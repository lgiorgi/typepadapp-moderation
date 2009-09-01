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
})