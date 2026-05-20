// Подключаем заголовочные файлы стандартной библиотеки
#include <iostream>  // Для ввода-вывода (cout, cerr)
#include <string>    // Для работы со строками (std::string)
#include <curl/curl.h>  // Библиотека libcurl для HTTP запросов
#include <nlohmann/json.hpp>  // Библиотека для работы с JSON (nlohmann/json)

// Создаем псевдоним для удобства работы с JSON библиотекой
using json = nlohmann::json;

// Функция обратного вызова для записи данных, полученных от curl
static size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    // contents - указатель на полученные данные
    // size - размер одного элемента
    // nmemb - количество элементов
    // userp - указатель на строку для сохранения данных
    ((std::string*)userp)->append((char*)contents, size * nmemb);  // Добавляем данные в строку
    return size * nmemb;  // Возвращаем количество обработанных байт
}

// Функция выполнения GET запроса и парсинга JSON ответа
json performGetRequest(const std::string& url) {
    CURL* curl = curl_easy_init();  // Инициализируем сессию curl
    std::string response_string;  // Строка для хранения ответа сервера
    if (curl) {  // Если инициализация успешна
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());  // Устанавливаем URL запроса
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);  // Устанавливаем callback для записи
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_string);  // Передаем указатель на строку для сохранения
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);  // Устанавливаем таймаут 30 секунд
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);  // Следовать за редиректами
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);  // Отключаем проверку SSL сертификата (упрощение)
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);  // Отключаем проверку имени хоста (упрощение)
        CURLcode res = curl_easy_perform(curl);  // Выполняем запрос
        if (res != CURLE_OK) {  // Если произошла ошибка
            std::cerr << "HTTP error: " << curl_easy_strerror(res) << std::endl;  // Выводим ошибку
            curl_easy_cleanup(curl);  // Очищаем ресурсы curl
            return json();  // Возвращаем пустой JSON
        }
        curl_easy_cleanup(curl);  // Очищаем ресурсы curl
    }
    try {
        return json::parse(response_string);  // Парсим JSON и возвращаем объект
    } catch (...) {  // Если парсинг не удался
        return json();  // Возвращаем пустой JSON
    }
}

// Главная функция программы
int main(int argc, char* argv[]) {
    // Проверяем количество аргументов командной строки
    if (argc < 3 || argc > 4) {  // Нужно 2 или 3 аргумента (жанры, API ключ, необязательно страница)
        std::cerr << "Usage: " << argv[0] << " \"<genres_comma_separated>\" <API_KEY> [page]" << std::endl;
        return 1;  // Выход с кодом ошибки
    }
    std::string genres = argv[1];  // Первый аргумент - строка жанров (через запятую)
    std::string apiKey = argv[2];  // Второй аргумент - API ключ RAWG
    int page = 1;  // Номер страницы результатов (по умолчанию 1)
    if (argc == 4) {  // Если передан третий аргумент
        page = std::stoi(argv[3]);  // Преобразуем его в число
    }

    std::string url;  // Переменная для URL запроса
    // Формируем URL в зависимости от параметров
    if (genres.empty() || genres == "popular") {  // Если жанры не указаны или "popular"
        // Запрос популярных игр (сортировка по рейтингу)
        url = "https://api.rawg.io/api/games?ordering=-rating&page_size=20&page=" + std::to_string(page) + "&key=" + apiKey;
    } else {
        // Инициализируем curl для URL-кодирования параметра genres
        CURL* curl = curl_easy_init();
        // Кодируем строку жанров для безопасной передачи в URL
        char* encoded = curl_easy_escape(curl, genres.c_str(), (int)genres.length());
        std::string encodedGenres(encoded);  // Преобразуем в std::string
        curl_free(encoded);  // Освобождаем память, выделенную curl_easy_escape
        curl_easy_cleanup(curl);  // Очищаем curl
        // Запрос игр по жанрам, сортировка по рейтингу
        url = "https://api.rawg.io/api/games?genres=" + encodedGenres +
              "&ordering=-rating&page_size=20&page=" + std::to_string(page) + "&key=" + apiKey;
    }

    json resp = performGetRequest(url);  // Выполняем запрос и получаем JSON
    // Проверяем, что ответ содержит поле "results" и оно является массивом
    if (!resp.contains("results") || !resp["results"].is_array()) {
        return 1;  // Выход с ошибкой
    }

    // Перебираем все игры в результатах
    for (auto& game : resp["results"]) {
        // Проверяем наличие обязательных полей
        if (!game.contains("id") || !game["id"].is_number()) continue;  // Пропускаем если нет ID
        if (!game.contains("name") || !game["name"].is_string()) continue;  // Пропускаем если нет названия
        int id = game["id"].get<int>();  // Получаем ID игры
        std::string name = game["name"].get<std::string>();  // Получаем название игры
        std::string genre = "";  // Переменная для жанра (по умолчанию пустая)
        // Проверяем наличие жанров у игры
        if (game.contains("genres") && game["genres"].is_array() && !game["genres"].empty()) {
            auto& firstGenre = game["genres"][0];  // Берем первый жанр
            if (firstGenre.contains("name") && firstGenre["name"].is_string()) {
                genre = firstGenre["name"].get<std::string>();  // Получаем название жанра
            }
        }
        // Выводим результат в формате: ID|Название|Жанр (разделитель |)
        std::cout << id << "|" << name << "|" << genre << std::endl;
    }
    return 0;  // Успешное завершение
}