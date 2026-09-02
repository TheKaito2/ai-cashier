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
            document.getElementById('todayRevenue').textContent = `฿${analytics.today_revenue.toFixed(2)}`;

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
                    <div class="prod">
                        <div class="prod__dot" aria-hidden="true">
                            <svg class="icon" viewBox="0 0 24 24"><path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/></svg>
                        </div>
                        <div>
                            <div class="prod__name">${product.name}</div>
                            <div class="prod__meta">${product.size || product.id}</div>
                        </div>
                    </div>
                </td>
                <td>${product.category}${product.restricted && product.restricted !== 'none'
                    ? ` <span class="status-badge status-low" title="Alcohol: 11:00-24:00, staff ID check. Tobacco: staff-only, never displayed.">${product.restricted}</span>` : ''}</td>
                <td class="num">฿${product.price.toFixed(2)}</td>
                <td class="num">${product.stock} <span class="prod__meta">/ min ${product.min_stock}</span></td>
                <td>
                    <span class="status-badge ${this.getStatusClass(product)}">
                        ${this.getStatusText(product)}
                    </span>
                </td>
                <td>
                    <button class="btn btn-secondary" onclick="inventoryManager.showRestockModal('${product.id}')">
                        + Restock
                    </button>
                </td>
            </tr>
        `).join('');
    }

    getStatusClass(product) {
        if (product.stock === 0) return 'status-out';
        if (product.stock <= product.min_stock) return 'status-low';
        return 'status-good';
    }

    getStatusText(product) {
        if (product.stock === 0) return 'Out of Stock';
        if (product.stock <= product.min_stock) return 'Low Stock';
        return 'In Stock';
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