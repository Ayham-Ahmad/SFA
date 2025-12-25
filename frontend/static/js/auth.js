/**
 * auth.js
 * Centralized Authentication Logic.
 */

const Auth = {
    /**
     * Login with username and password
     */
    async login(username, password) {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch('/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });

        if (!response.ok) {
            throw new Error('Invalid credentials');
        }

        const data = await response.json();
        this.setSession(data);
        return data;
    },

    /**
     * Logout and clear session
     */
    logout() {
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('username');
        window.location.href = '/login';
    },

    /**
     * Save session data to localStorage
     */
    setSession(data) {
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('role', data.role);
        localStorage.setItem('username', data.username);
    },

    getToken() {
        return localStorage.getItem('token');
    },

    getRole() {
        return localStorage.getItem('role');
    },

    getUsername() {
        return localStorage.getItem('username');
    },

    isAuthenticated() {
        return !!this.getToken();
    },

    /**
     * Enforce authentication on protected pages
     */
    requireAuth() {
        if (!this.isAuthenticated() && window.location.pathname !== '/login') {
            window.location.href = '/login';
        }
    },

    /**
     * Check if user is admin
     */
    isAdmin() {
        return this.getRole() === 'admin';
    }
};

// Auto-check on load (if not on login page)
if (window.location.pathname !== '/login') {
    Auth.requireAuth();
}
