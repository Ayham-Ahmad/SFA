document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorMsg = document.getElementById('error-msg');

    try {
        const data = await Auth.login(username, password);

        if (data.role === 'admin') {
            window.location.href = '/admin';
        } else {
            window.location.href = '/manager';
        }
    } catch (error) {
        errorMsg.textContent = error.message || 'Login failed';
        errorMsg.style.display = 'block';
    }
});
