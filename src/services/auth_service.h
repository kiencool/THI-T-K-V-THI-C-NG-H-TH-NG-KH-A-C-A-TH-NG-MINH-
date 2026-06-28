#pragma once
#include <string>
#include <vector>
#include <mutex>

// Thông tin thẻ RFID đã đăng ký
struct Card {
    std::string uid;
    std::string time_added;
};

// Dịch vụ xác thực: quản lý thẻ RFID, mã PIN, quyền admin
namespace AuthService {
    void load_registered_cards();
    void load_passwords();
    bool find_card(const std::string& uid, std::string& time_added);
    void enroll_card(const std::string& uid);
    bool verify_tenant_pin(const char* pin);
    bool verify_admin_pin(const char* pin);
    bool is_admin_card(const std::string& uid);

    // Thread-safe access to card list
    extern std::vector<Card> registered_cards;
    extern std::mutex cards_mutex;
}
