#include <iostream>
#include <string>
#include <vector>
#include <curl/curl.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

struct Game {
    int id;
    std::string name;
};

static size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    ((std::string*)userp)->append((char*)contents, size * nmemb);
    return size * nmemb;
}

json performGetRequest(const std::string& url) {
    CURL* curl = curl_easy_init();
    std::string response_string;
    json response_json;

    if (!curl) {
        std::cerr << "[DEBUG] Не удалось инициализировать CURL" << std::endl;
        return response_json;
    }

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_string);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);

    std::cerr << "[DEBUG] Выполняю запрос: " << url << std::endl;
    CURLcode res = curl_easy_perform(curl);
    if (res != CURLE_OK) {
        std::cerr << "[DEBUG] Ошибка HTTP запроса: " << curl_easy_strerror(res) << std::endl;
        curl_easy_cleanup(curl);
        return json();
    }

    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    std::cerr << "[DEBUG] HTTP код ответа: " << http_code << std::endl;
    curl_easy_cleanup(curl);

    try {
        response_json = json::parse(response_string);
        std::cerr << "[DEBUG] JSON успешно распарсен" << std::endl;
    } catch (const json::parse_error& e) {
        std::cerr << "[DEBUG] Ошибка парсинга JSON: " << e.what() << std::endl;
        return json();
    }

    return response_json;
}

int main(int argc, char* argv[]) {
    std::cerr << "[DEBUG] Программа запущена, аргументов: " << argc << std::endl;
    if (argc != 3) {
        std::cerr << "Использование: " << argv[0] << " \"<жанр1,жанр2>\" <API_КЛЮЧ_RAWG>" << std::endl;
        return 1;
    }

    std::string genres = argv[1];
    std::string apiKey = argv[2];
    std::cerr << "[DEBUG] Жанры: " << genres << ", API ключ: " << apiKey.substr(0, 4) << "..." << std::endl;

    CURL* curl = curl_easy_init();
    if (!curl) {
        std::cerr << "[DEBUG] Не удалось инициализировать CURL для escape" << std::endl;
        return 1;
    }
    char* encodedGenres = curl_easy_escape(curl, genres.c_str(), (int)genres.length());
    std::string encodedGenresStr(encodedGenres);
    curl_free(encodedGenres);
    curl_easy_cleanup(curl);

    std::string url = "https://api.rawg.io/api/games?search=" + encodedGenresStr +
                  "&ordering=-rating&page_size=10&key=" + apiKey;
    std::cerr << "[DEBUG] Сформированный URL: " << url << std::endl;

    json response = performGetRequest(url);
    if (response.is_null() || !response.contains("results") || !response["results"].is_array()) {
        std::cerr << "[DEBUG] Не удалось получить список игр или он пуст." << std::endl;
        return 1;
    }

    std::vector<Game> games;
    for (auto& game_json : response["results"]) {
        Game game;
        game.id = game_json["id"].get<int>();
        game.name = game_json["name"].get<std::string>();
        games.push_back(game);
    }

    std::cerr << "[DEBUG] Найдено игр: " << games.size() << std::endl;
    for (const auto& game : games) {
        std::cout << game.id << "|" << game.name << std::endl;
    }
    return 0;
}