// DiffusionBot Chart.js configurations

const CHART_COLORS = {
    primary: '#0ea5e9',
    success: '#059669',
    danger: '#dc2626',
    warning: '#d97706',
    info: '#8b5cf6',
    gray: '#6b7280',
    primaryBg: 'rgba(14, 165, 233, 0.1)',
    successBg: 'rgba(5, 150, 105, 0.1)',
    dangerBg: 'rgba(220, 38, 38, 0.1)',
};

const CHART_DEFAULTS = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            display: true,
            position: 'bottom',
            labels: { font: { size: 12 }, padding: 16, usePointStyle: true }
        },
        tooltip: {
            backgroundColor: '#1f2937',
            titleFont: { size: 13 },
            bodyFont: { size: 12 },
            padding: 10,
            cornerRadius: 8,
        }
    },
    scales: {
        x: {
            grid: { display: false },
            ticks: { font: { size: 11 }, color: '#9ca3af' }
        },
        y: {
            grid: { color: '#f3f4f6' },
            ticks: { font: { size: 11 }, color: '#9ca3af' }
        }
    }
};

// Line chart: evolution over time (backlinks, traffic, DA)
function createLineChart(canvasId, labels, datasets) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            ...CHART_DEFAULTS,
            elements: {
                line: { tension: 0.3, borderWidth: 2 },
                point: { radius: 3, hoverRadius: 5 }
            }
        }
    });
}

// Bar chart: comparisons (platforms, projects)
function createBarChart(canvasId, labels, datasets) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            ...CHART_DEFAULTS,
            scales: {
                ...CHART_DEFAULTS.scales,
                y: { ...CHART_DEFAULTS.scales.y, beginAtZero: true }
            }
        }
    });
}

// Doughnut chart: distribution (dofollow/nofollow, status)
function createDoughnutChart(canvasId, labels, data, colors) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: colors || [CHART_COLORS.success, CHART_COLORS.danger, CHART_COLORS.warning, CHART_COLORS.info],
                borderWidth: 0,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { font: { size: 12 }, padding: 16, usePointStyle: true } }
            },
            cutout: '65%',
        }
    });
}
