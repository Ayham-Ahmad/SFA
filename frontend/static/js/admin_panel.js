/**
 * Admin Panel JavaScript
 * =======================
 * Handles user management CRUD operations for the admin panel.
 */

let userModal;
let deleteUserId = null;

// Toast notification helper
function showToast(message, type = 'error') {
    // Remove existing toast if any
    const existing = document.querySelector('.admin-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `admin-toast alert alert-${type === 'error' ? 'danger' : 'success'} position-fixed`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px; animation: fadeIn 0.3s ease;';
    toast.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas fa-${type === 'error' ? 'exclamation-circle' : 'check-circle'} me-2"></i>
            <span>${message}</span>
            <button type="button" class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
        </div>
    `;
    document.body.appendChild(toast);

    // Auto-remove after 4 seconds
    setTimeout(() => toast.remove(), 4000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Check if user is admin, redirect if not
    if (typeof Auth !== 'undefined' && Auth.getRole() !== 'admin') {
        window.location.href = '/manager';
        return;
    }

    userModal = new bootstrap.Modal(document.getElementById('userModal'));
    fetchUsers();
});

/**
 * Show the Add User modal with empty fields.
 */
function showAddUser() {
    document.getElementById('userModalLabel').innerText = 'Add User';
    document.getElementById('userId').value = '';
    document.getElementById('username').value = '';
    document.getElementById('password').value = '';
    document.getElementById('role').value = 'manager';
    document.getElementById('user-error-msg').style.display = 'none';
    userModal.show();
}

/**
 * Show the Edit User modal with pre-filled data.
 */
function showEditUser(id, name, role) {
    document.getElementById('userModalLabel').innerText = 'Edit User';
    document.getElementById('userId').value = id;
    document.getElementById('username').value = name;
    document.getElementById('password').value = '';
    document.getElementById('role').value = role;
    document.getElementById('user-error-msg').style.display = 'none';
    userModal.show();
}

/**
 * Save (create or update) a user.
 */
async function saveUser() {
    const id = document.getElementById('userId').value;
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const role = document.getElementById('role').value;

    const token = localStorage.getItem('token');
    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/users/${id}` : '/api/users';

    const payload = { username, role };
    if (password) payload.password = password;

    try {
        const res = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            userModal.hide();
            showToast(id ? 'User updated successfully' : 'User created successfully', 'success');
            fetchUsers();
        } else {
            const error = await res.json();
            const errorMsg = document.getElementById('user-error-msg');
            errorMsg.textContent = error.detail || 'Failed to save user.';
            errorMsg.style.display = 'block';
        }
    } catch (e) {
        console.error('Save user error:', e);
        const errorMsg = document.getElementById('user-error-msg');
        errorMsg.textContent = 'An error occurred while saving the user.';
        errorMsg.style.display = 'block';
    }
}

/**
 * Show delete confirmation modal.
 */
function deleteUser(id, username) {
    deleteUserId = id;
    document.getElementById('deleteUserName').textContent = username || 'this user';
    const modal = new bootstrap.Modal(document.getElementById('deleteUserModal'));
    modal.show();
}

/**
 * Confirm and execute user deletion.
 */
async function confirmDeleteUser() {
    if (!deleteUserId) return;

    bootstrap.Modal.getInstance(document.getElementById('deleteUserModal')).hide();

    const token = localStorage.getItem('token');
    try {
        const res = await fetch(`/api/users/${deleteUserId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (res.ok) {
            showToast('User deleted successfully', 'success');
            fetchUsers();
        } else {
            showToast('Failed to delete user.');
        }
    } catch (e) {
        console.error('Delete user error:', e);
    }

    deleteUserId = null;
}

/**
 * Format datetime for display.
 */
function formatDateTime(dateStr) {
    if (!dateStr) return '<span class="text-muted">Never</span>';
    const date = new Date(dateStr);
    return date.toLocaleString();
}

/**
 * Fetch and display all users.
 */
async function fetchUsers() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    try {
        const response = await fetch('/api/users', {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            const users = await response.json();
            renderUsersTable(users);
        } else if (response.status === 401) {
            window.location.href = '/login';
        }
    } catch (error) {
        console.error('Fetch users error:', error);
    }
}

/**
 * Render the users table with data.
 */
function renderUsersTable(users) {
    const tbody = document.getElementById('users-table-body');
    tbody.innerHTML = '';

    users.forEach(user => {
        const row = document.createElement('tr');
        const roleBadgeClass = user.role === 'admin' ? 'bg-danger' : 'bg-success';

        row.innerHTML = `
            <th scope="row">${user.id}</th>
            <td>${escapeHtml(user.username)}</td>
            <td><span class="badge ${roleBadgeClass}">${user.role.toUpperCase()}</span></td>
            <td>${new Date(user.created_at).toLocaleDateString()}</td>
            <td>${formatDateTime(user.last_login)}</td>
            <td>
                <button class="btn btn-sm btn-outline-secondary" 
                    onclick="showEditUser('${user.id}', '${escapeHtml(user.username)}', '${user.role}')">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" 
                    onclick="deleteUser('${user.id}', '${escapeHtml(user.username)}')">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

/**
 * Escape HTML to prevent XSS.
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
