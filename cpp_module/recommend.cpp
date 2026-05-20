#include <iostream>
#include <string>
#include <curl/curl.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

static size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    ((std::string*)userp)->append((char*)contents, size * nmemb);
    return size * nmemb;
}

json performGetRequest(const std::string& url) {
    CURL* curl = curl_easy_init();
    std::string response_string;
    if (curl) {
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_string);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);
        CURLcode res = curl_easy_perform(curl);
        if (res != CURLE_OK) {
            std::cerr << "HTTP error: " << curl_easy_strerror(res) << std::endl;
            curl_easy_cleanup(curl);
            return json();
        }
        curl_easy_cleanup(curl);
    }
    try {
        return json::parse(response_string);
    } catch (...) {
        return json();
    }
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Usage: " << argv[0] << " \"<genres_comma_separated>\" <API_KEY>" << std::endl;
        return 1;
    }
    std::string genres = argv[1];
    std::string apiKey = argv[2];

    std::string url;
    if (genres.empty() || genres == "popular") {
        // Запрос без фильтрации по жанрам – просто топовые игры
        url = "https://api.rawg.io/api/games?ordering=-rating&page_size=10&key=" + apiKey;
    } else {
        // Кодируем строку жанров (например "rpg,action")
        CURL* curl = curl_easy_init();
        char* encoded = curl_easy_escape(curl, genres.c_str(), (int)genres.length());
        std::string encodedGenres(encoded);
        curl_free(encoded);
        curl_easy_cleanup(curl);
        url = "https://api.rawg.io/api/games?genres=" + encodedGenres +
              "&ordering=-rating&page_size=10&key=" + apiKey;
    }

    json resp = performGetRequest(url);
    if (!resp.contains("results") || !resp["results"].is_array()) {
        return 1;
    }

    for (auto& game : resp["results"]) {
        if (!game.contains("id") || !game["id"].is_number()) continue;
        if (!game.contains("name") || !game["name"].is_string()) continue;
        int id = game["id"].get<int>();
        std::string name = game["name"].get<std::string>();
        std::string genre = "";
        if (game.contains("genres") && game["genres"].is_array() && !game["genres"].empty()) {
            auto& firstGenre = game["genres"][0];
            if (firstGenre.contains("name") && firstGenre["name"].is_string()) {
                genre = firstGenre["name"].get<std::string>();
            }
        }
        std::cout << id << "|" << name << "|" << genre << std::endl;
    }
    return 0;
}