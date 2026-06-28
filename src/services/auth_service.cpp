#include "auth_service.h"
#include "config/config.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <cstring>
#include <ctime>

namespace AuthService {

std::vector<Card> registered_cards;
std::mutex cards_mutex;

void load_registered_cards() {
    std::lock_guard<std::mutex> lock(cards_mutex);
    registered_cards.clear();
    std::ifstream f(RFID_CARDS_FILE);
    if (f.is_open()) {
        std::string line;
        while (std::getline(f, line)) {
            size_t delim = line.find('|');
            if (delim != std::string::npos) {
                Card c;
                c.uid = line.substr(0, delim);
                c.time_added = line.substr(delim + 1);
                c.uid.erase(c.uid.find_last_not_of(" \n\r\t") + 1);
                c.time_added.erase(c.time_added.find_last_not_of(" \n\r\t") + 1);
                registered_cards.push_back(c);
            }
        }
        f.close();
    }
    std::cout << "[SYSTEM] Loaded " << registered_cards.size() << " cards from DB.\n";
}

bool find_card(const std::string& uid, std::string& time_added) {
    std::lock_guard<std::mutex> lock(cards_mutex);
    for (const auto& c : registered_cards) {
        if (c.uid == uid) {
            time_added = c.time_added;
            return true;
        }
    }
    return false;
}

void enroll_card(const std::string& uid) {
    std::time_t t = std::time(nullptr);
    char time_str[100];
    std::strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", std::localtime(&t));

    std::ofstream f(RFID_CARDS_FILE, std::ios::app);
    if (f.is_open()) {
        f << uid << "|" << time_str << "\n";
        f.close();
    }
    // Tải lại danh sách thẻ sau khi thêm thẻ mới
    load_registered_cards();
}

bool verify_tenant_pin(const char* pin) {
    return std::strcmp(pin, TENANT_PIN) == 0;
}

bool verify_admin_pin(const char* pin) {
    return std::strcmp(pin, ADMIN_PIN) == 0;
}

bool is_admin_card(const std::string& uid) {
    return uid == ADMIN_CARD_UID;
}

} // namespace AuthService
