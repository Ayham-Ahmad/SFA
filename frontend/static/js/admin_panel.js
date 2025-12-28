/**
 * Admin Panel JavaScript
 * =======================
 * Handles user management CRUD operations for the admin panel.
 */

let userModal;
let deleteUserId = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
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
            fetchUsers();
        } else {
            const error = await res.json();
            alert(error.detail || 'Failed to save user.');
        }
    } catch (e) {
        console.error('Save user error:', e);
        alert('An error occurred while saving the user.');
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
            fetchUsers();
        } else {
            alert('Failed to delete user.');
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
