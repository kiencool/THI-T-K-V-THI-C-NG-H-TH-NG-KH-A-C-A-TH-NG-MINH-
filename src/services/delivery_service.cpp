#include "delivery_service.h"
#include "config/config.h"
#include <fstream>
#include <vector>
#include <iostream>

namespace DeliveryService {

bool verify_and_consume_code(const std::string& code, std::string& creator_name) {
    if (code.empty()) return false;

    bool matched = false;
    creator_name = "Unknown";
    std::vector<std::string> remaining_codes;

    std::ifstream f(DELIVERY_CODES_FILE);
    if (f.is_open()) {
        std::string line;
        while (std::getline(f, line)) {
            line.erase(line.find_last_not_of(" \n\r\t") + 1);
            if (line.empty()) continue;

            size_t delim = line.find('|');
            std::string c_code = line;
            std::string c_creator = "Unknown";
            if (delim != std::string::npos) {
                c_code = line.substr(0, delim);
                c_creator = line.substr(delim + 1);
            }

            if (c_code == code) {
                matched = true;
                creator_name = c_creator;
            } else {
                remaining_codes.push_back(line);
            }
        }
        f.close();
    }

    // Ghi lại file mã giao hàng, bỏ mã đã sử dụng
    if (matched) {
        std::ofstream out(DELIVERY_CODES_FILE);
        for (const auto& c : remaining_codes) out << c << "\n";
        out.close();
    }

    return matched;
}

} // namespace DeliveryService
