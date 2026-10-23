(function () {
    'use strict';

    var text = document.getElementById('aspReplyText');
    var counter = document.getElementById('aspReplyCount');
    var replyForm = document.getElementById('aspReplyForm');
    var replyBtn = document.getElementById('aspReplyBtn');
    var statusForm = document.getElementById('aspStatusForm');

    if (text && counter) {
        text.addEventListener('input', function () { counter.textContent = String(text.value.length); });
    }

    if (replyForm) {
        replyForm.addEventListener('submit', function (e) {
            if (!text.value.trim()) {
                e.preventDefault();
                if (window.showToast) window.showToast('Please write a response first.', 'error');
                text.focus();
                return;
            }
            replyBtn.disabled = true;
            replyBtn.textContent = 'Sending…';
        });
    }

    if (statusForm) {
        statusForm.addEventListener('submit', function (e) {
            var select = statusForm.querySelector('select');
            var label = select.options[select.selectedIndex].text;
            if (!window.confirm('Change this request\u2019s status to "' + label + '"?')) {
                e.preventDefault();
            }
        });
    }
})();