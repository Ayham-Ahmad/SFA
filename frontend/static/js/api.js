/**
 * api.js
 * Centralized API handling for SFA Frontend.
 * Wraps fetch with automatic token injection and error handling.
 */

const API = {
    baseUrl: '', // Relative paths used in this app

    /**
     * Generic fetch wrapper
     * @param {string} endpoint - URL endpoint (e.g. '/api/data')
     * @param {object} options - Fetch options
     * @returns {Promise<any>} - JSON response or throws error
     */
    async request(endpoint, options = {}) {
        const token = localStorage.getItem('token');

        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const config = {
            ...options,
            headers
        };

        try {
            const response = await fetch(endpoint, config);

            // Handle 401 Unauthorized globally
            if (response.status === 401) {
                // If we are not on login page, redirect
                if (!window.location.pathname.includes('/login')) {
                    localStorage.removeItem('token');
                    window.location.href = '/login';
                }
                throw new Error('Unauthorized');
            }

            // For 204 No Content
            if (response.status === 204) {
                return null;
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || data.detail || `Error ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            throw error;
        }
    },

    get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    },

    post(endpoint, body) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(body)
        });
    },

    // Special handler for form data (no JSON content-type)
    postForm(endpoint, formData) {
        return fetch(endpoint, {
            method: 'POST',
            body: formData
            // Content-Type header is set automatically by browser for FormData
        });
    }
};
