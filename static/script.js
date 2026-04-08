const API_BASE = 'http://localhost:8000';
let token = null;

function showAuth() {
    document.getElementById('auth-section').style.display = 'block';
    document.getElementById('collection-section').style.display = 'none';
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

// Регистрация
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

// Логин
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
            token = data.access_token;
            document.getElementById('auth-error').textContent = '';
            showCollection();
        } else {
            const error = await res.json();
            document.getElementById('auth-error').textContent = error.detail;
        }
    } catch (error) {
        document.getElementById('auth-error').textContent = 'Сетевая ошибка';
    }
};

// Добавление игры
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

// Рекомендации
document.getElementById('getRecommendationsBtn').onclick = getRecommendations;

// Выход
document.getElementById('logoutBtn').onclick = () => {
    token = null;
    showAuth();
};

// Начальное состояние
showAuth();