$(document).ready(function () {
    if (window.localStorage) {
        if (!location.pathname.startsWith('/search/'))
        {
            // Load from local storage:
            id = 'searchForm_' + location.pathname;
            storedValue = localStorage[id];
            if (storedValue) {
                persistenceData = JSON.parse(storedValue);
                $(".textinput,.select", "form.searchform").each(function () {
                    $(this).val(persistenceData[this.id]);
                });
                $(".checkboxinput", "form.searchform").each(function () {
                    $(this).prop('checked', persistenceData[this.id]);
                });
            }
            // Save to local storage:
            $('form.searchform').submit(function (e) {
                persistenceData = new Object();
                $(".textinput,.select", "form.searchform").each(function () {
                    persistenceData[this.id] = $(this).val();
                });
                $(".checkboxinput", "form.searchform").each(function () {
                    persistenceData[this.id] = $(this).prop('checked');
                });
                localStorage[id] = JSON.stringify(persistenceData);
            });
        }
    }
});
