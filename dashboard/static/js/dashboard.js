// DiffusionBot Dashboard JS

document.addEventListener('DOMContentLoaded', function() {
    // Highlight active nav link
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        const href = link.getAttribute('href');
        if (currentPath === href || (href !== '/dashboard/' && currentPath.startsWith(href))) {
            link.classList.add('active');
        }
    });

    // HTMX after-swap: reinit charts if needed
    document.body.addEventListener('htmx:afterSwap', function(e) {
        if (typeof initCharts === 'function') {
            initCharts();
        }
    });
});

// Utility: format numbers with locale
function formatNumber(n) {
    return new Intl.NumberFormat('fr-FR').format(n);
}

// Utility: badge class for post status
function statusBadge(status) {
    return `<span class="badge badge-${status}">${status}</span>`;
}
