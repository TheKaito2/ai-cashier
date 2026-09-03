// Light or dark, remembered in the shop settings and in this browser, and
// broadcast to the other open tabs.
class ThemeManager {
    constructor() {
        this.currentTheme = 'light';
        this.init();
    }

    init() {
        this.loadTheme();
        window.addEventListener('storage', (e) => {
            if (e.key === 'theme') this.setTheme(e.newValue, false);
        });
    }

    async loadTheme() {
        const saved = localStorage.getItem('theme');
        if (saved) {
            this.setTheme(saved, false);
            return;
        }
        try {
            const data = await fetch('/api/theme').then(r => r.json());
            this.setTheme(data.theme, false);
        } catch (error) {
            console.error('Error loading theme:', error);
        }
    }

    setTheme(theme, broadcast = true) {
        this.currentTheme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        document.querySelectorAll('[data-theme-toggle]').forEach(btn => {
            btn.textContent = theme === 'dark' ? 'Light' : 'Dark';
        });
        if (broadcast) {
            fetch('/api/theme', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ theme })
            });
        }
    }

    toggle() {
        this.setTheme(this.currentTheme === 'light' ? 'dark' : 'light');
    }
}

const themeManager = new ThemeManager();

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-theme-toggle]').forEach(btn => {
        btn.onclick = () => themeManager.toggle();
        btn.textContent = themeManager.currentTheme === 'dark' ? 'Light' : 'Dark';
    });
});
