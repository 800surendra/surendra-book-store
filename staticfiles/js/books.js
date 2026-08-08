document.addEventListener('DOMContentLoaded', function() {

    // Wishlist toggle
    document.querySelectorAll('.wishlist-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            this.classList.toggle('active');
            const icon = this.querySelector('i');
            icon.classList.toggle('bi-heart');
            icon.classList.toggle('bi-heart-fill');
        });
    });

    // Auto-submit filters on change
    const form = document.getElementById('filterForm');
    if (form) {
        form.querySelectorAll('select, input[type="checkbox"]').forEach(function(el) {
            el.addEventListener('change', function() {
                form.submit();
            });
        });
        let timer;
        form.querySelectorAll('.filter-price input[type="number"]').forEach(function(inp) {
            inp.addEventListener('input', function() {
                clearTimeout(timer);
                timer = setTimeout(function() { form.submit(); }, 500);
            });
        });
    }

    // Mobile filter toggle
    const toggleBtn = document.getElementById('filterToggleMobile');
    const bar = document.getElementById('filterBar');
    if (toggleBtn && bar) {
        toggleBtn.addEventListener('click', function() {
            const groups = bar.querySelectorAll('.filter-group:not(.filter-search):not(.filter-actions)');
            const expanded = bar.classList.toggle('filter-expanded');
            groups.forEach(function(g) {
                g.style.display = expanded ? '' : 'none';
            });
            this.innerHTML = expanded ? '<i class="bi bi-x-lg"></i> Close' : '<i class="bi bi-sliders2"></i> Filters';
        });
        // Init on small screens
        if (window.innerWidth < 768) {
            const groups = bar.querySelectorAll('.filter-group:not(.filter-search):not(.filter-actions)');
            groups.forEach(function(g) { g.style.display = 'none'; });
        }
        window.addEventListener('resize', function() {
            if (window.innerWidth >= 768) {
                const groups = bar.querySelectorAll('.filter-group:not(.filter-search):not(.filter-actions)');
                groups.forEach(function(g) { g.style.display = ''; });
                bar.classList.remove('filter-expanded');
                toggleBtn.innerHTML = '<i class="bi bi-sliders2"></i> Filters';
            } else if (!bar.classList.contains('filter-expanded')) {
                const groups = bar.querySelectorAll('.filter-group:not(.filter-search):not(.filter-actions)');
                groups.forEach(function(g) { g.style.display = 'none'; });
            }
        });
    }
});