// One masthead for every page. v2 pasted the header into each file, which is
// how admin.html ended up with an unclosed <button> and a nav that pointed at
// the wrong pages.
(function () {
    const LINKS = [
        ['/inventory', 'Inventory'],
        ['/admin',     'Analytics'],
        ['/monitor',   'Monitor'],
    ];
    const here = location.pathname;
    const host = document.querySelector('[data-mast]');
    if (!host) return;

    host.className = 'mast';
    host.innerHTML =
        '<span class="mast__dot" aria-hidden="true"></span>' +
        '<a class="mast__name" href="/" style="text-decoration:none;color:inherit">AI Cashier</a>' +
        '<span class="mast__where">Group 3 &middot; Assumption College Sriracha</span>' +
        '<nav class="mast__nav header-nav" aria-label="Main">' +
        LINKS.map(([href, text]) =>
            `<a href="${href}"${href === here ? ' aria-current="page" style="color:var(--text-primary)"' : ''}>${text}</a>`
        ).join('') +
        '</nav>';
})();
