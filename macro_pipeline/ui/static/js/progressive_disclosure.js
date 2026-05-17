// L8 D9 — Progressive disclosure JS for L1/L2/L3 explanation stack.
// Per Strategic L8 pre-flight 2026-05-16. Vision §11 BINDING for all outputs.

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.explanation-toggle').forEach(function (toggle) {
        toggle.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = toggle.getAttribute('data-target');
            const target = document.getElementById(targetId);
            if (target) {
                target.classList.toggle('expanded');
                toggle.textContent = target.classList.contains('expanded')
                    ? '− Less'
                    : '+ More';
            }
        });
    });
});
