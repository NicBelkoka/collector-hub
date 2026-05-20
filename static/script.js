const API_BASE = 'http://localhost:8000';
let token = null;
let tempToken = null;

function showAuth() {
    document.getElementById('auth-section').style.display = 'block';
    document.getElementById('collection-section').style.display = 'none';
    document.getElementById('recommendationsResult').innerHTML = '';
    token = null;
    tempToken = null;
    document.getElementById('twofa-section').style.display = 'none';
    document.getElementById('twofa-error').textContent = '';
}

function showCollection() {
    document.getElementById('auth-section').style.display = 'none';
    document.getElementById('collection-section').style.display = 'block';
    loadGames();
    update2faButton();
}

async function loadGames() {
    try {
        const res = await fetch(`${API_BASE}/games`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
            const games = await res.json();
            const list = document.getElementById('gamesList');
            list.innerHTML = '';
            games.forEach(g => {
                const li = document.createElement('li');
                li.innerHTML = `
                    ${g.title} (${g.genre})
                    <button class="delete-game-btn" data-id="${g.id}" style="margin-left: 10px; background-color: #dc3545; padding: 2px 8px; border-radius: 4px;">Удалить</button>
                `;
                list.appendChild(li);
            });
            // Навешиваем обработчики на кнопки удаления
            document.querySelectorAll('.delete-game-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const gameId = btn.dataset.id;
                    if (confirm('Удалить игру из коллекции?')) {
                        await deleteGame(gameId);
                    }
                });
            });
        }
    } catch(e) { console.error(e); }
}

async function deleteGame(gameId) {
    try {
        const res = await fetch(`${API_BASE}/games/${gameId}`, {
            method: 'DELETE',
            headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
            // Обновляем список игр и рекомендации (чтобы удалённая игра могла снова рекомендоваться)
            await loadGames();
            await getRecommendations();  // если хотите мгновенно обновить рекомендации
        } else {
            const err = await res.json();
            alert('Ошибка удаления: ' + err.detail);
        }
    } catch(e) {
        alert('Сетевая ошибка при удалении');
    }
}

async function update2faButton() {
    try {
        const res = await fetch(`${API_BASE}/user/2fa-status`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            const btn = document.getElementById('enable2faBtn');
            if (data.enabled) {
                btn.style.display = 'none';
                document.getElementById('twofa-setup').style.display = 'none';
            } else {
                btn.style.display = 'inline-block';
            }
        }
    } catch(e) { console.error(e); }
}

async function getRecommendations() {
    const resultDiv = document.getElementById('recommendationsResult');
    resultDiv.innerHTML = '<p>Загрузка...</p>';
    try {
        const res = await fetch(`${API_BASE}/recommendations`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
            const games = await res.json();
            console.log('Received games:', games); // <- отладка
            resultDiv.innerHTML = '<h4>✨ Рекомендованные игры</h4>';
            if (!games.length) {
                resultDiv.innerHTML += '<p>Нет новых рекомендаций</p>';
                return;
            }
            games.forEach(game => {
                console.log('Adding game:', game); // <- отладка
                const div = document.createElement('div');
                div.className = 'recommendation-item';
                div.innerHTML = `
                    <span>${game.name} (${game.genre})</span>
                    <button class="add-rec-btn" data-id="${game.id}" data-name="${game.name}" data-genre="${game.genre}">➕ Добавить</button>
                `;
                resultDiv.appendChild(div);
            });
            // Вешаем обработчики на кнопки
            document.querySelectorAll('.add-rec-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const id = parseInt(btn.dataset.id);
                    const name = btn.dataset.name;
                    const genre = btn.dataset.genre;
                    await addGameFromRecommendation(id, name, genre);
                });
            });
        } else {
            const err = await res.json();
            resultDiv.innerHTML = `<p class="error">Ошибка: ${err.detail}</p>`;
        }
    } catch(e) {
        resultDiv.innerHTML = `<p class="error">Сетевая ошибка</p>`;
        console.error(e);
    }
}

async function addGameFromRecommendation(externalId, title, genre) {
    try {
        const res = await fetch(`${API_BASE}/games`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`
            },
            body: JSON.stringify({ title, genre, external_id: externalId })
        });
        if (res.ok) {
            // Обновить коллекцию и перезапросить рекомендации
            await loadGames();
            await getRecommendations();
        } else {
            const err = await res.json();
            alert('Ошибка добавления: ' + err.detail);
        }
    } catch(e) {
        alert('Сетевая ошибка');
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
        if (res.ok) alert('Регистрация успешна! Войдите.');
        else {
            const err = await res.json();
            document.getElementById('auth-error').textContent = err.detail;
        }
    } catch(e) { document.getElementById('auth-error').textContent = 'Ошибка сети'; }
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
            if (data.twofa_required) {
                tempToken = data.access_token;
                document.getElementById('twofa-section').style.display = 'block';
                document.getElementById('twofa-code').focus();
            } else {
                token = data.access_token;
                showCollection();
            }
        } else {
            const err = await res.json();
            document.getElementById('auth-error').textContent = err.detail;
        }
    } catch(e) { document.getElementById('auth-error').textContent = 'Ошибка сети'; }
};

// Подтверждение 2FA при входе
document.getElementById('verify2faBtn').onclick = async () => {
    const code = document.getElementById('twofa-code').value;
    if (!code) { document.getElementById('twofa-error').textContent = 'Введите код'; return; }
    try {
        const res = await fetch(`${API_BASE}/login-2fa`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ temp_token: tempToken, code })
        });
        if (res.ok) {
            const data = await res.json();
            token = data.access_token;
            showCollection();
        } else {
            const err = await res.json();
            document.getElementById('twofa-error').textContent = err.detail;
        }
    } catch(e) { document.getElementById('twofa-error').textContent = 'Ошибка сети'; }
};

// Добавление игры вручную
document.getElementById('addGameForm').onsubmit = async (e) => {
    e.preventDefault();
    const title = document.getElementById('title').value;
    const genre = document.getElementById('genre').value;
    if (!genre) {
        alert('Выберите жанр');
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/games`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`
            },
            body: JSON.stringify({ title, genre })
        });
        if (res.ok) {
            document.getElementById('addGameForm').reset();
            loadGames();
        } else {
            const err = await res.json();
            alert('Ошибка: ' + err.detail);
        }
    } catch(e) { alert('Сетевая ошибка'); }
};

// Рекомендации
document.getElementById('getRecommendationsBtn').onclick = getRecommendations;

// Включение 2FA (QR)
document.getElementById('enable2faBtn').onclick = async () => {
    try {
        const res = await fetch(`${API_BASE}/enable-2fa`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const img = document.createElement('img');
            img.src = url;
            img.style.maxWidth = '200px';
            const secretRes = await fetch(`${API_BASE}/get-2fa-secret`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            let secret = '';
            if (secretRes.ok) {
                const sdata = await secretRes.json();
                secret = sdata.secret;
            }
            const setupDiv = document.getElementById('twofa-setup');
            setupDiv.innerHTML = `
                <h4>Настройка 2FA</h4>
                <p>Секрет: ${secret}</p>
                <div id="qr-container"></div>
                <input type="text" id="twofa-verify-code" placeholder="Код подтверждения">
                <button id="confirm2faBtn">Активировать</button>
            `;
            document.getElementById('qr-container').appendChild(img);
            setupDiv.style.display = 'block';
            document.getElementById('confirm2faBtn').onclick = async () => {
                const code = document.getElementById('twofa-verify-code').value;
                if (!code) { alert('Введите код'); return; }
                const verRes = await fetch(`${API_BASE}/verify-2fa`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        Authorization: `Bearer ${token}`
                    },
                    body: JSON.stringify({ code })
                });
                if (verRes.ok) {
                    alert('2FA активирована!');
                    setupDiv.style.display = 'none';
                    update2faButton();
                } else {
                    const err = await verRes.json();
                    alert('Ошибка: ' + err.detail);
                }
            };
        } else {
            const err = await res.json();
            alert('Ошибка: ' + err.detail);
        }
    } catch(e) { alert('Сетевая ошибка'); }
};

// Выход
document.getElementById('logoutBtn').onclick = () => {
    token = null;
    tempToken = null;
    showAuth();
};

// Начало
showAuth();