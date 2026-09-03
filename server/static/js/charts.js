// Inline SVG charts, no library.  The shop counter may have no internet, and
// tests/test_pages.py refuses any URL in this folder - so the markup is a
// string the browser parses, not createElementNS with a namespace string.
const Charts = (() => {
    const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    const fmt = n => Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
    const W = 600;

    // vertical columns, one per bucket: series = [{label, value, cls?}]
    function columns(el, series, { height = 170, unit = '' } = {}) {
        if (!series.length || !series.some(s => s.value > 0)) {
            el.innerHTML = '<p class="chart__empty">nothing yet</p>';
            return;
        }
        const H = height, padB = 22, padT = 18, gap = 4;
        const n = series.length, cw = (W - gap * (n - 1)) / n;
        const max = Math.max(...series.map(s => s.value)) || 1;
        const every = n > 16 ? Math.ceil(n / 12) : 1;
        const body = series.map((s, i) => {
            const h = Math.round((H - padB - padT) * s.value / max);
            const x = i * (cw + gap), y = H - padB - h;
            const label = i % every === 0
                ? `<text class="axis" x="${x + cw / 2}" y="${H - 6}" text-anchor="middle">${esc(s.label)}</text>` : '';
            const value = s.value > 0 && n <= 16
                ? `<text class="val" x="${x + cw / 2}" y="${y - 5}" text-anchor="middle">${esc(unit + fmt(s.value))}</text>` : '';
            return `<rect class="track" x="${x}" y="${padT}" width="${cw}" height="${H - padB - padT}" rx="2"/>` +
                   `<rect class="bar ${s.cls || ''}" x="${x}" y="${y}" width="${cw}" height="${h}" rx="2">` +
                   `<title>${esc(s.label)}: ${esc(unit + fmt(s.value))}</title></rect>${value}${label}`;
        }).join('');
        el.innerHTML = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(el.dataset.label || 'chart')}">${body}</svg>`;
    }

    // horizontal bars: label left, value right; series = [{label, value, valueText?, cls?}]
    function bars(el, series, { unit = '', max: fixedMax } = {}) {
        if (!series.length) {
            el.innerHTML = '<p class="chart__empty">nothing yet</p>';
            return;
        }
        const rowH = 30, labelW = 210, valW = 96, H = series.length * rowH;
        const max = fixedMax || Math.max(...series.map(s => s.value)) || 1;
        const body = series.map((s, i) => {
            const y = i * rowH + 7;
            const w = Math.max(2, Math.round((W - labelW - valW - 12) * Math.min(s.value, max) / max));
            const label = s.label.length > 28 ? s.label.slice(0, 27) + '…' : s.label;
            return `<text class="axis" x="0" y="${y + 12}">${esc(label)}</text>` +
                   `<rect class="track" x="${labelW}" y="${y}" width="${W - labelW - valW - 12}" height="16" rx="2"/>` +
                   `<rect class="bar ${s.cls || ''}" x="${labelW}" y="${y}" width="${w}" height="16" rx="2">` +
                   `<title>${esc(s.label)}: ${esc(s.valueText ?? unit + fmt(s.value))}</title></rect>` +
                   `<text class="val" x="${W}" y="${y + 12}" text-anchor="end">${esc(s.valueText ?? unit + fmt(s.value))}</text>`;
        }).join('');
        el.innerHTML = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(el.dataset.label || 'chart')}">${body}</svg>`;
    }

    // sale rows -> the last `days` days, oldest first
    function byDay(rows, days = 14, value = r => r.total) {
        const out = [], today = new Date();
        today.setHours(0, 0, 0, 0);
        for (let d = days - 1; d >= 0; d--) {
            const day = new Date(today);
            day.setDate(today.getDate() - d);
            out.push({ key: day.toDateString(), label: day.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }), value: 0 });
        }
        const index = Object.fromEntries(out.map((b, i) => [b.key, i]));
        rows.forEach(r => {
            const key = new Date(r.timestamp).toDateString();
            if (key in index) out[index[key]].value += value(r);
        });
        return out;
    }

    // sale rows -> 24 hour buckets
    function byHour(rows, value = () => 1) {
        const out = Array.from({ length: 24 }, (_, h) => ({ label: String(h).padStart(2, '0'), value: 0 }));
        rows.forEach(r => { out[new Date(r.timestamp).getHours()].value += value(r); });
        return out;
    }

    return { columns, bars, byDay, byHour, fmt };
})();
