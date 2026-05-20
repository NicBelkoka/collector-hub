// Базовый URL для API (локальный сервер на порту 8000)
const API_BASE = 'http://localhost:8000';
// Переменная для хранения основного JWT токена
let token = null;
// Переменная для хранения временного JWT токена (при 2FA)
let tempToken = null;

// Функция отображения формы авторизации (скрывает коллекцию)
function showAuth() {
    // Показываем секцию авторизации
    document.getElementById('auth-section').style.display = 'block';
    // Скрываем секцию коллекции игр
    document.getElementById('collection-section').style.display = 'none';
    // Очищаем блок рекомендаций
    document.getElementById('recommendationsResult').innerHTML = '';
    // Сбрасываем токены
    token = null;
    tempToken = null;
    // Скрываем секцию ввода 2FA
    document.getElementById('twofa-section').style.display = 'none';
    // Очищаем текст ошибки 2FA
    document.getElementById('twofa-error').textContent = '';
}

// Функция отображения коллекции игр (скрывает форму входа)
function showCollection() {
    // Скрываем секцию авторизации
    document.getElementById('auth-section').style.display = 'none';
    // Показываем секцию коллекции
    document.getElementById('collection-section').style.display = 'block';
    // Загружаем список игр пользователя
    loadGames();
    // Обновляем статус кнопки 2FA
    update2faButton();
}

// Асинхронная функция загрузки списка игр пользователя
async function loadGames() {
    try {
        // Отправляем GET запрос к /games с токеном в заголовке
        const res = await fetch(`${API_BASE}/games`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        // Если запрос успешен (200-299)
        if (res.ok) {
            const games = await res.json();  // Парсим JSON ответ
            const list = document.getElementById('gamesList');  // Получаем контейнер списка
            list.innerHTML = '';  // Очищаем список
            // Перебираем все игры и создаем элементы списка
            games.forEach(g => {
                const li = document.createElement('li');  // Создаем элемент <li>
                li.innerHTML = `
                    ${g.title} (${g.genre})
                    <button class="delete-game-btn" data-id="${g.id}" style="margin-left: 10px; background-color: #dc3545; padding: 2px 8px; border-radius: 4px;">Удалить</button>
                `;
                list.appendChild(li);  // Добавляем в список
            });
            // Навешиваем обработчики на все кнопки удаления
            document.querySelectorAll('.delete-game-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const gameId = btn.dataset.id;  // Получаем ID игры из data-id атрибута
                    if (confirm('Удалить игру из коллекции?')) {  // Подтверждение от пользователя
                        await deleteGame(gameId);  // Вызываем функцию удаления
                    }
                });
            });
        }
    } catch(e) { console.error(e); }  // Логируем ошибки в консоль
}

// Асинхронная функция удаления игры по ID
async function deleteGame(gameId) {
    try {
        // Отправляем DELETE запрос
        const res = await fetch(`${API_BASE}/games/${gameId}`, {
            method: 'DELETE',
            headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
            // Обновляем список игр и рекомендации
            await loadGames();  // Перезагружаем список
            await getRecommendations();  // Обновляем рекомендации
        } else {
            const err = await res.json();  // Получаем ошибку от сервера
            alert('Ошибка удаления: ' + err.detail);  // Показываем alert
        }
    } catch(e) {
        alert('Сетевая ошибка при удалении');  // Ошибка сети
    }
}

// Асинхронная функция обновления статуса кнопки 2FA
async function update2faButton() {
    try {
        // Запрашиваем статус 2FA пользователя
        const res = await fetch(`${API_BASE}/user/2fa-status`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            const btn = document.getElementById('enable2faBtn');  // Кнопка включения 2FA
            if (data.enabled) {
                btn.style.display = 'none';  // Если 2FA включена - скрываем кнопку
                document.getElementById('twofa-setup').style.display = 'none';  // Скрываем настройку
            } else {
                btn.style.display = 'inline-block';  // Показываем кнопку
            }
        }
    } catch(e) { console.error(e); }
}

// Асинхронная функция получения рекомендаций
async function getRecommendations() {
    const resultDiv = document.getElementById('recommendationsResult');
    resultDiv.innerHTML = '<p>Загрузка...</p>';  // Показываем индикатор загрузки
    try {
        // Запрашиваем рекомендации
        const res = await fetch(`${API_BASE}/recommendations`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
            const games = await res.json();
            console.log('Received games:', games);  // Отладка в консоль
            resultDiv.innerHTML = '<h4>✨ Рекомендованные игры</h4>';
            if (!games.length) {
                resultDiv.innerHTML += '<p>Нет новых рекомендаций</p>';
                return;
            }
            // Перебираем все рекомендованные игры
            games.forEach(game => {
                console.log('Adding game:', game);  // Отладка
                const div = document.createElement('div');
                div.className = 'recommendation-item';
                div.innerHTML = `
                    <span>${game.name} (${game.genre})</span>
                    <button class="add-rec-btn" data-id="${game.id}" data-name="${game.name}" data-genre="${game.genre}">➕ Добавить</button>
                `;
                resultDiv.appendChild(div);
            });
            // Навешиваем обработчики на кнопки добавления
            document.querySelectorAll('.add-rec-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const id = parseInt(btn.dataset.id);  // ID игры в RAWG
                    const name = btn.dataset.name;  // Название игры
                    const genre = btn.dataset.genre;  // Жанр
                    await addGameFromRecommendation(id, name, genre);  // Добавляем игру
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

// Асинхронная функция добавления игры из рекомендаций
async function addGameFromRecommendation(externalId, title, genre) {
    try {
        // Отправляем POST запрос для добавления игры
        const res = await fetch(`${API_BASE}/games`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`
            },
            body: JSON.stringify({ title, genre, external_id: externalId })
        });
        if (res.ok) {
            // Обновляем коллекцию и рекомендации
            await loadGames();  // Перезагружаем список игр
            await getRecommendations();  // Обновляем рекомендации
        } else {
            const err = await res.json();
            alert('Ошибка добавления: ' + err.detail);
        }
    } catch(e) {
        alert('Сетевая ошибка');
    }
}

// Обработчик кнопки регистрации
document.getElementById('registerBtn').onclick = async () => {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    try {
        const res = await fetch(`${API_BASE}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        if (res.ok) alert('Регистрация успешна! Войдите.');  // Успех
        else {
            const err = await res.json();
            document.getElementById('auth-error').textContent = err.detail;  // Показываем ошибку
        }
    } catch(e) { document.getElementById('auth-error').textContent = 'Ошибка сети'; }
};

// Обработчик кнопки входа (логин)
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
            if (data.twofa_required) {  // Если требуется 2FA
                tempToken = data.access_token;  // Сохраняем временный токен
                document.getElementById('twofa-section').style.display = 'block';  // Показываем форму 2FA
                document.getElementById('twofa-code').focus();  // Фокус на поле ввода кода
            } else {
                token = data.access_token;  // Сохраняем обычный токен
                showCollection();  // Показываем коллекцию
            }
        } else {
            const err = await res.json();
            document.getElementById('auth-error').textContent = err.detail;
        }
    } catch(e) { document.getElementById('auth-error').textContent = 'Ошибка сети'; }
};

// Обработчик кнопки подтверждения 2FA при входе
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
            token = data.access_token;  // Получаем постоянный токен
            showCollection();  // Показываем коллекцию
        } else {
            const err = await res.json();
            document.getElementById('twofa-error').textContent = err.detail;
        }
    } catch(e) { document.getElementById('twofa-error').textContent = 'Ошибка сети'; }
};

// Обработчик формы добавления игры вручную
document.getElementById('addGameForm').onsubmit = async (e) => {
    e.preventDefault();  // Отменяем стандартную отправку формы
    const title = document.getElementById('title').value;
    const genre = document.getElementById('genre').value;
    if (!genre) {
        alert('Выберите жанр');  // Проверка выбора жанра
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
            document.getElementById('addGameForm').reset();  // Очищаем форму
            loadGames();  // Обновляем список игр
        } else {
            const err = await res.json();
            alert('Ошибка: ' + err.detail);
        }
    } catch(e) { alert('Сетевая ошибка'); }
};

// Назначение обработчика для кнопки получения рекомендаций
document.getElementById('getRecommendationsBtn').onclick = getRecommendations;

// Обработчик кнопки включения 2FA (генерация QR-кода)
document.getElementById('enable2faBtn').onclick = async () => {
    try {
        // Запрашиваем QR-код
        const res = await fetch(`${API_BASE}/enable-2fa`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
            const blob = await res.blob();  // Получаем изображение QR-кода
            const url = URL.createObjectURL(blob);  // Создаем URL для изображения
            const img = document.createElement('img');
            img.src = url;
            img.style.maxWidth = '200px';
            // Получаем секрет для ручного ввода
            const secretRes = await fetch(`${API_BASE}/get-2fa-secret`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            let secret = '';
            if (secretRes.ok) {
                const sdata = await secretRes.json();
                secret = sdata.secret;
            }
            const setupDiv = document.getElementById('twofa-setup');
            // Отображаем форму активации 2FA
            setupDiv.innerHTML = `
                <h4>Настройка 2FA</h4>
                <p>Секрет: ${secret}</p>
                <div id="qr-container"></div>
                <input type="text" id="twofa-verify-code" placeholder="Код подтверждения">
                <button id="confirm2faBtn">Активировать</button>
            `;
            document.getElementById('qr-container').appendChild(img);  // Добавляем QR-код
            setupDiv.style.display = 'block';
            // Обработчик кнопки активации 2FA
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
                    update2faButton();  // Обновляем статус кнопки
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

// Обработчик кнопки выхода из системы
document.getElementById('logoutBtn').onclick = () => {
    token = null;  // Сбрасываем токен
    tempToken = null;  // Сбрасываем временный токен
    showAuth();  // Показываем форму авторизации
};

// Начальная инициализация: показываем форму авторизации
showAuth();