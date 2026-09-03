// Analytics Dashboard
class AdminDashboard {
    constructor() {
        this.analytics = null;
        this.init();
    }

    async init() {
        await this.loadAnalytics();
        await this.loadRecentTransactions();
        setInterval(() => {
            this.loadAnalytics();
            this.loadRecentTransactions();
        }, 30000);
    }

    async loadAnalytics() {
        try {
            const [analytics, sales] = await Promise.all([
                fetch('/api/analytics').then(r => r.json()),
                fetch('/api/sales?limit=500').then(r => r.json()),
            ]);
            this.analytics = analytics;
            this.updateMetrics(sales);
            this.drawCharts(sales);
            this.createBestSellersRanking();
        } catch (error) {
            console.error('Error loading analytics:', error);
        }
    }

    updateMetrics(sales) {
        const { analytics } = this;
        document.getElementById('totalRevenue').textContent = `฿${analytics.total_revenue.toFixed(2)}`;
        document.getElementById('todaySales').textContent = analytics.today_sales;
        const avgOrder = analytics.total_sales > 0 ? analytics.total_revenue / analytics.total_sales : 0;
        document.getElementById('avgOrder').textContent = `฿${avgOrder.toFixed(2)}`;

        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        let todayRevenue = 0, yesterdayRevenue = 0;
        sales.forEach(sale => {
            const day = new Date(sale.timestamp);
            day.setHours(0, 0, 0, 0);
            if (day.getTime() === today.getTime()) todayRevenue += sale.total;
            else if (day.getTime() === yesterday.getTime()) yesterdayRevenue += sale.total;
        });
        let growth = 0;
        if (yesterdayRevenue > 0) growth = ((todayRevenue - yesterdayRevenue) / yesterdayRevenue) * 100;
        else if (todayRevenue > 0) growth = 100;

        document.getElementById('revenueGrowth').textContent = `${Math.abs(growth).toFixed(1)}%`;
        const up = growth >= 0;
        document.getElementById('growthArrow').textContent = up ? '\u25B2' : '\u25BC';
        const growthContainer = document.getElementById('growthContainer');
        growthContainer.classList.toggle('up', up);
        growthContainer.classList.toggle('down', !up);
    }

    drawCharts(sales) {
        Charts.columns(document.getElementById('dayChart'), Charts.byDay(sales, 14), { unit: '฿' });
        Charts.columns(document.getElementById('hourChart'), Charts.byHour(sales), { height: 150 });
    }

    createBestSellersRanking() {
        const container = document.getElementById('bestSellersRanking');
        if (!this.analytics || this.analytics.total_sales === 0) {
            container.innerHTML = '<p class="empty">No sales recorded yet</p>';
            return;
        }
        const rows = this.analytics.top_products.slice(0, 8).map((p, i) => ({
            label: `${i + 1}  ${p.product_name}`, value: p.revenue,
            valueText: `฿${Charts.fmt(p.revenue)} · ${p.quantity_sold} sold`,
        }));
        Charts.bars(container, rows);
    }

    async loadRecentTransactions() {
        try {
            const response = await fetch('/api/sales?limit=10');
            const sales = await response.json();
            
            const container = document.getElementById('recentTransactions');
            
            if (sales.length === 0) {
                container.innerHTML = '<p class="empty">No sales yet</p>';
                return;
            }
            
            container.innerHTML = sales.map(sale => {
                const date = new Date(sale.timestamp);
                return `
                    <div class="txn">
                        <div>
                            <div class="txn__id">${sale.id}</div>
                            <div class="txn__when">${date.toLocaleString('en-GB', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'})}</div>
                        </div>
                        <div class="txn__amt">฿${sale.total.toFixed(2)}</div>
                    </div>
                `;
            }).join('');
        } catch (error) {
            console.error('Error loading transactions:', error);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new AdminDashboard();
});