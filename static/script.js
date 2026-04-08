const API_BASE = 'http://localhost:8000';
let token = null;
let tempToken = null;

function showAuth() {
    document.getElementById('auth-section').style.display = 'block';
    document.getElementById('collection-section').style.display = 'none';
    document.getElementById('twofa-section').style.display = 'none';
    document.getElementById('twofa-error').textContent = '';
}

function showCollection() {
    document.getElementById('auth-section').style.display = 'none';
    document.getElementById('collection-section').style.display = 'block';
    loadGames();
}

async function loadGames() {
    try {
        const res = await fetch(`${API_BASE}/games`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            const games = await res.json();
            const list = document.getElementById('gamesList');
            list.innerHTML = '';
            games.forEach(game => {
                const li = document.createElement('li');
                li.textContent = `${game.title} (${game.genre})`;
                list.appendChild(li);
            });
        } else {
            console.error('Не удалось загрузить игры');
        }
    } catch (error) {
        console.error('Ошибка загрузки игр:', error);
    }
}

async function getRecommendations() {
    const resultDiv = document.getElementById('recommendationsResult');
    resultDiv.innerHTML = '<p>Загрузка рекомендаций...</p>';
    try {
        const res = await fetch(`${API_BASE}/recommendations`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            const games = await res.json();
            resultDiv.innerHTML = '<h4>✨ Рекомендованные игры:</h4>';
            games.forEach(game => {
                const gameDiv = document.createElement('div');
                gameDiv.className = 'recommendation-item';
                gameDiv.textContent = `${game.name} (${game.genre})`;
                resultDiv.appendChild(gameDiv);
            });
        } else {
            const error = await res.json();
            resultDiv.innerHTML = `<p class="error">Ошибка: ${error.detail}</p>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<p class="error">Сетевая ошибка: ${error.message}</p>`;
    }
}

document.getElementById('registerBtn').onclick = async () => {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    try {
        const res = await fetch(`${API_BASE}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        if (res.ok) {
            alert('Регистрация успешна! Теперь войдите.');
            document.getElementById('auth-error').textContent = '';
        } else {
            const error = await res.json();
            document.getElementById('auth-error').textContent = error.detail;
        }
    } catch (error) {
        document.getElementById('auth-error').textContent = 'Сетевая ошибка';
    }
};

document.getElementById('loginBtn').onclick = async () => {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    try {
        const res = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        if (res.ok) {
            const data = await res.json();
            if (data.twofa_required) {
                tempToken = data.access_token;
                document.getElementById('twofa-section').style.display = 'block';
                document.getElementById('auth-error').textContent = '';
                document.getElementById('twofa-code').value = '';
                document.getElementById('twofa-code').focus();
            } else {
                token = data.access_token;
                showCollection();
            }
        } else {
            const error = await res.json();
            document.getElementById('auth-error').textContent = error.detail;
        }
    } catch (error) {
        document.getElementById('auth-error').textContent = 'Сетевая ошибка';
    }
};

document.getElementById('verify2faBtn').onclick = async () => {
    const code = document.getElementById('twofa-code').value;
    if (!code) {
        document.getElementById('twofa-error').textContent = 'Введите код';
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/login-2fa`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ temp_token: tempToken, code: code })
        });
        if (res.ok) {
            const data = await res.json();
            token = data.access_token;
            document.getElementById('twofa-section').style.display = 'none';
            document.getElementById('twofa-error').textContent = '';
            showCollection();
        } else {
            const error = await res.json();
            document.getElementById('twofa-error').textContent = error.detail;
        }
    } catch (error) {
        document.getElementById('twofa-error').textContent = 'Сетевая ошибка';
    }
};

document.getElementById('addGameForm').onsubmit = async (e) => {
    e.preventDefault();
    const title = document.getElementById('title').value;
    const genre = document.getElementById('genre').value;
    try {
        const res = await fetch(`${API_BASE}/games`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ title, genre })
        });
        if (res.ok) {
            document.getElementById('addGameForm').reset();
            loadGames();
        } else {
            const error = await res.json();
            alert('Не удалось добавить игру: ' + error.detail);
        }
    } catch (error) {
        alert('Сетевая ошибка');
    }
};

document.getElementById('getRecommendationsBtn').onclick = getRecommendations;

document.getElementById('enable2faBtn').onclick = async () => {
    try {
        // Сначала получаем QR-код
        const resQr = await fetch(`${API_BASE}/enable-2fa`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (resQr.ok) {
            const blob = await resQr.blob();
            const url = URL.createObjectURL(blob);
            document.getElementById('twofa-qr').src = url;
            // Затем получаем секрет
            const resSecret = await fetch(`${API_BASE}/get-2fa-secret`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (resSecret.ok) {
                const secretData = await resSecret.json();
                document.getElementById('twofa-secret').textContent = secretData.secret;
                document.getElementById('twofa-setup').style.display = 'block';
            } else {
                alert('Ошибка получения секрета');
            }
        } else {
            const error = await resQr.json();
            alert('Ошибка: ' + error.detail);
        }
    } catch (error) {
        alert('Сетевая ошибка');
    }
};

document.getElementById('confirm2faBtn').onclick = async () => {
    const code = document.getElementById('twofa-verify-code').value;
    if (!code) {
        alert('Введите код из приложения');
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/verify-2fa`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ code: code })
        });
        if (res.ok) {
            alert('2FA успешно активирована! Теперь при следующем входе потребуется код.');
            document.getElementById('twofa-setup').style.display = 'none';
        } else {
            const error = await res.json();
            alert('Ошибка: ' + error.detail);
        }
    } catch (error) {
        alert('Сетевая ошибка');
    }
};

document.getElementById('logoutBtn').onclick = () => {
    token = null;
    tempToken = null;
    showAuth();
};

showAuth();