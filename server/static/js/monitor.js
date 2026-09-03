// The status board: is the till up, what did it last do, and what has it been
// refusing.  Everything comes from endpoints the other pages already use.
(function () {
    const $ = id => document.getElementById(id);
    const baht = n => '฿' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const when = iso => new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
    const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

    const KIND = { enrolment: 'ok', abstention: 'warn', override: 'info', basket_check: 'muted' };

    function describe(e) {
        switch (e.kind) {
            case 'enrolment':    return `${esc(e.sku_id)} taught from ${e.views} view${e.views === 1 ? '' : 's'}`;
            case 'abstention':   return `${esc(e.status)} · nearest ${esc(e.top_sku || '-')}` + (e.score != null ? ` at ${Number(e.score).toFixed(2)}` : '');
            case 'override':     return e.chosen ? `operator chose ${esc(e.chosen)}`
                                    : e.confirmed != null ? (e.confirmed ? 'ID check confirmed by staff' : 'ID check not confirmed')
                                    : e.expected_g != null ? `weight mismatch overridden · expected ${Math.round(e.expected_g)} g, pan ${Math.round(e.measured_g)} g`
                                    : 'staff override';
            case 'basket_check': return (e.ok ? 'weight ok' : 'WEIGHT MISMATCH') + ` · expected ${Math.round(e.expected_g)} g, pan ${Math.round(e.measured_g)} g`;
            default:             return esc(e.kind);
        }
    }

    function tile(id, cls, value, detail) {
        const el = $(id);
        el.className = 'tile ' + cls;
        el.querySelector('.tile__v').innerHTML = value;
        el.querySelector('.tile__d').textContent = detail;
    }

    async function refresh() {
        let status = null;
        try {
            status = await fetch('/api/system-status').then(r => r.json());
            tile('tTill', 'tile--ok', '<span class="beacon"></span>online', 'server time ' + when(status.timestamp));
            tile('tMode', status.lan ? 'tile--warn' : 'tile--ok', status.lan ? 'LAN' : 'loopback',
                 status.lan ? 'reachable on the shop network; writes need the PIN' : 'this machine only');
        } catch (e) {
            tile('tTill', 'tile--bad', '<span class="beacon beacon--off"></span>offline', 'the till process is not answering');
            console.error('status failed', e);
            return;
        }

        const [sales, events, products, analytics] = await Promise.all([
            fetch('/api/sales?limit=1').then(r => r.json()),
            fetch('/api/events?limit=200').then(r => r.json()),
            fetch('/api/products').then(r => r.json()),
            fetch('/api/analytics').then(r => r.json()),
        ]);

        tile('tProducts', analytics.low_stock_count ? 'tile--warn' : 'tile--ok', products.length,
             analytics.low_stock_count ? `${analytics.low_stock_count} at or below minimum` : 'none below minimum');
        if (sales.length) {
            tile('tSale', 'tile--ok', baht(sales[0].total), `${sales[0].items.length} line${sales[0].items.length === 1 ? '' : 's'} · ${when(sales[0].timestamp)}`);
        } else {
            tile('tSale', '', '–', 'no sale yet');
        }
        const abst = events.find(e => e.kind === 'abstention');
        tile('tAbstain', abst ? 'tile--warn' : 'tile--ok', abst ? esc(abst.status) : 'none',
             abst ? `nearest ${abst.top_sku || '-'} · ${when(abst.timestamp)}` : 'nothing refused in the last 200 events');
        const enrol = events.filter(e => e.kind === 'enrolment').length;
        tile('tEnrol', 'tile--ok', enrol, enrol ? 'products taught, in the last 200 events' : 'nothing taught yet');

        const counts = {};
        events.forEach(e => { counts[e.kind] = (counts[e.kind] || 0) + 1; });
        Charts.bars($('kindsChart'), Object.entries(counts).map(([k, v]) => ({
            label: k.replace('_', ' '), value: v, cls: KIND[k] === 'warn' ? 'bar--warn' : '' })));
        Charts.columns($('abstainChart'), Charts.byDay(events.filter(e => e.kind === 'abstention'), 14, () => 1), { height: 150 });

        const list = $('events');
        list.innerHTML = events.length ? events.slice(0, 14).map(e =>
            `<div class="event"><span class="event__when">${when(e.timestamp)}</span>` +
            `<span><span class="chip chip--${KIND[e.kind] || 'muted'}">${esc(e.kind.replace('_', ' '))}</span></span>` +
            `<span>${describe(e)}</span></div>`).join('')
            : '<p class="empty">no events logged yet</p>';
    }

    refresh();
    setInterval(refresh, 5000);
})();
