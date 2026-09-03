// Inventory Management
class InventoryManager {
    constructor() {
        this.products = [];
        this.currentFilter = 'all';
        this.searchQuery = '';
        this.selectedProductId = null;
        this.init();
    }

    async init() {
        this.bindEvents();
        await this.loadData();
        setInterval(() => this.loadData(), 30000);
    }

    bindEvents() {
        document.getElementById('searchInput').addEventListener('input', (e) => {
            this.searchQuery = e.target.value.toLowerCase();
            this.renderProducts();
        });

        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentFilter = btn.dataset.filter;
                this.renderProducts();
            });
        });
    }

    async loadData() {
        try {
            const productsRes = await fetch('/api/products');
            this.products = await productsRes.json();

            const analyticsRes = await fetch('/api/analytics');
            const analytics = await analyticsRes.json();

            document.getElementById('totalProducts').textContent = this.products.length;
            document.getElementById('lowStockCount').textContent = analytics.low_stock_count;
            document.getElementById('todayRevenue').textContent = '฿' + Charts.fmt(analytics.today_revenue);

            this.renderProducts();
        } catch (error) {
            console.error('Error loading data:', error);
        }
    }

    renderProducts() {
        const tbody = document.getElementById('productsTableBody');
        
        let filteredProducts = this.products;
        
        if (this.currentFilter !== 'all') {
            filteredProducts = filteredProducts.filter(p => p.category === this.currentFilter);
        }
        
        if (this.searchQuery) {
            filteredProducts = filteredProducts.filter(p => 
                p.name.toLowerCase().includes(this.searchQuery) ||
                p.category.toLowerCase().includes(this.searchQuery)
            );
        }

        tbody.innerHTML = filteredProducts.map(product => `
            <tr>
                <td>
                    <div class="prod__name">${product.name}</div>
                    <div class="prod__meta">${product.size || product.id}</div>
                </td>
                <td>${product.category}${product.restricted && product.restricted !== 'none'
                    ? ` <span class="chip chip--warn" title="Alcohol: 11:00-24:00, staff ID check. Tobacco: staff-only, never displayed.">${product.restricted}</span>` : ''}</td>
                <td class="num">฿${product.price.toFixed(2)}</td>
                <td class="num">${product.stock} <span class="prod__meta">/ min ${product.min_stock}</span></td>
                <td><span class="chip ${this.getStatusClass(product)}">${this.getStatusText(product)}</span></td>
                <td class="num">
                    <button class="btn btn-secondary" onclick="inventoryManager.showRestockModal('${product.id}')">+ Restock</button>
                </td>
            </tr>
        `).join('');
        this.renderCover();
    }

    // stock against its minimum, the products nearest to running out first
    renderCover() {
        const rows = [...this.products]
            .sort((a, b) => (a.stock / Math.max(a.min_stock, 1)) - (b.stock / Math.max(b.min_stock, 1)))
            .slice(0, 10)
            .map(p => ({ label: p.name, value: p.stock, valueText: `${p.stock} / ${p.min_stock}`,
                         cls: p.stock === 0 ? 'bar--bad' : p.stock <= p.min_stock ? 'bar--warn' : '' }));
        Charts.bars(document.getElementById('coverChart'), rows,
                    { max: Math.max(...this.products.map(p => p.stock), 1) });
    }

    getStatusClass(product) {
        if (product.stock === 0) return 'chip--bad';
        if (product.stock <= product.min_stock) return 'chip--warn';
        return 'chip--ok';
    }

    getStatusText(product) {
        if (product.stock === 0) return 'Out';
        if (product.stock <= product.min_stock) return 'Low';
        return 'In stock';
    }

    showRestockModal(productId) {
        const product = this.products.find(p => p.id === productId);
        if (!product) return;

        this.selectedProductId = productId;
        document.getElementById('restockProductName').textContent = product.name;
        document.getElementById('restockQuantity').value = '';
        document.getElementById('restockModal').style.display = 'block';
        document.getElementById('restockQuantity').focus();
    }

    async confirmRestock() {
        const quantity = parseInt(document.getElementById('restockQuantity').value);
        if (!quantity || quantity <= 0) {
            alert('Please enter a valid quantity');
            return;
        }

        try {
            // off the loopback interface the server wants the shop's dashboard PIN
            const headers = {};
            const pin = localStorage.getItem('dashboardPin');
            if (pin) headers['X-Dashboard-Pin'] = pin;
            const response = await fetch(`/api/restock/${this.selectedProductId}?quantity=${quantity}`, {
                method: 'POST', headers
            });

            if (response.status === 401) {
                const entered = prompt('Dashboard PIN (set in the shop settings):');
                if (entered) {
                    localStorage.setItem('dashboardPin', entered);
                    return this.confirmRestock();
                }
                return;
            }

            if (response.ok) {
                this.closeRestockModal();
                await this.loadData();
            } else {
                alert('Failed to restock product');
            }
        } catch (error) {
            console.error('Error restocking:', error);
            alert('Error restocking product');
        }
    }

    closeRestockModal() {
        document.getElementById('restockModal').style.display = 'none';
        this.selectedProductId = null;
    }
}

function closeRestockModal() {
    window.inventoryManager.closeRestockModal();
}

function confirmRestock() {
    window.inventoryManager.confirmRestock();
}

document.addEventListener('DOMContentLoaded', () => {
    window.inventoryManager = new InventoryManager();
});