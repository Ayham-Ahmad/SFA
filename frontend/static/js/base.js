var el = document.getElementById("wrapper");
var toggleButton = document.getElementById("menu-toggle");

if (toggleButton) {
    toggleButton.onclick = function () {
        el.classList.toggle("toggled");
    };
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('username');
    window.location.href = '/login';
}

// Theme Logic
function getPreferredTheme() {
    const storedTheme = localStorage.getItem('theme');
    if (storedTheme) {
        return storedTheme;
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function setTheme(theme) {
    if (theme === 'auto') {
        if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
            document.documentElement.setAttribute('data-bs-theme', 'dark');
        } else {
            document.documentElement.setAttribute('data-bs-theme', 'light');
        }
        localStorage.removeItem('theme'); // Auto means no manual override
    } else {
        document.documentElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem('theme', theme);
    }
    updateActiveTheme(theme);
}

function updateActiveTheme(theme) {
    // Update radio buttons
    const actualTheme = theme === 'auto' ? 'auto' : theme;
    const btn = document.querySelector(`[name="theme-options"][value="${actualTheme}"]`);
    if (btn) btn.checked = true;
}

// Init Theme
const savedTheme = localStorage.getItem('theme') || 'auto';
setTheme(savedTheme);

// Listen for system changes if auto
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (!localStorage.getItem('theme')) {
        setTheme('auto');
    }
});

// Auth Check (Simple client-side check, real auth is on backend)
const token = localStorage.getItem('token');
const role = localStorage.getItem('role');

if (!token && window.location.pathname !== '/login') {
    window.location.href = '/login';
}

// Hide Admin Panel for non-admins
const adminLink = document.getElementById('admin-link');
if (adminLink && role !== 'admin') {
    adminLink.style.display = 'none';
}

// --- NEW: Fetch User Info for Welcome Message ---
async function fetchUserInfo() {
    if (!token) return;
    try {
        const response = await fetch('/users/me', {
            headers: { 'Authorization': `Bearer ${token}` } // Sends the JWT "ID Card"
        });
        if (response.ok) {
            const user = await response.json();
            const welcomeDiv = document.getElementById('user-welcome');
            if (welcomeDiv) {
                welcomeDiv.textContent = `Welcome, ${user.username}`;
            }
        }
    } catch (e) {
        console.error("Failed to fetch user info", e);
    }
}

// Call it immediately
fetchUserInfo();
