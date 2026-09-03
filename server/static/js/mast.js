// One masthead for every page. v2 pasted the header into each file, which is
// how admin.html ended up with an unclosed <button> and a nav that pointed at
// the wrong pages.  The theme button lives here too; theme.js wires it.
(function () {
    const LINKS = [
        ['/',          'Overview'],
        ['/inventory', 'Inventory'],
        ['/admin',     'Analytics'],
        ['/monitor',   'Monitor'],
    ];
    const here = location.pathname;
    const host = document.querySelector('[data-mast]');
    if (!host) return;

    host.className = 'mast';
    host.innerHTML =
        '<a class="mast__name" href="/">AI Cashier</a>' +
        '<span class="mast__where">Group 3 &middot; Assumption College Sriracha</span>' +
        '<nav class="mast__nav" aria-label="Main">' +
        LINKS.map(([href, text]) =>
            `<a href="${href}"${href === here ? ' aria-current="page"' : ''}>${text}</a>`
        ).join('') +
        '<button class="theme-btn" type="button" data-theme-toggle aria-label="Switch theme">Dark</button>' +
        '</nav>';
})();
