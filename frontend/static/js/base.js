/**
 * base.js - Shared UI Logic
 * Handles Theme, Sidebar, and Global Utilities.
 */

// ============================================================================
// Theme Management
// ============================================================================

const Theme = {
    init() {
        const savedTheme = localStorage.getItem('theme') || 'auto';
        this.set(savedTheme);

        // Listen for system changes if in auto mode
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (localStorage.getItem('theme') === 'auto') {
                this.apply(e.matches ? 'dark' : 'light');
            }
        });
    },

    set(theme) {
        localStorage.setItem('theme', theme);
        if (theme === 'auto') {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            this.apply(prefersDark ? 'dark' : 'light');
        } else {
            this.apply(theme);
        }
    },

    apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        // Force redraw if needed (sometimes required for plots)
        // Dispatch event for other components (like Graphs)
        window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
    },

    getColors() {
        const style = getComputedStyle(document.documentElement);
        return {
            text: style.getPropertyValue('--text-color').trim(),
            bg: style.getPropertyValue('--bg-color').trim(),
            cardBg: style.getPropertyValue('--card-bg').trim(),
            border: style.getPropertyValue('--border-color').trim(),
            grid: style.getPropertyValue('--light-text').trim() || '#ccc'
        };
    }
};

// ============================================================================
// Sidebar & UI
// ============================================================================

document.addEventListener("DOMContentLoaded", function () {
    // 1. Sidebar Toggle
    var el = document.getElementById("wrapper");
    var toggleButton = document.getElementById("menu-toggle");

    if (toggleButton) {
        toggleButton.onclick = function () {
            el.classList.toggle("toggled");
        };
    }

    // 2. Initialize Theme
    Theme.init();

    // 3. User Info & Admin Link (If Auth module is present)
    if (typeof Auth !== 'undefined' && Auth.isAuthenticated()) {
        const role = Auth.getRole();
        const username = Auth.getUsername();

        // Update Welcome Message
        const welcomeEl = document.getElementById('user-welcome');
        if (welcomeEl && username) {
            welcomeEl.textContent = `Welcome, ${username}`;
        }

        // Show Admin Link if admin
        if (role === 'admin') {
            const adminLink = document.getElementById('admin-link');
            if (adminLink) adminLink.style.display = 'block';
        }
    }
});
