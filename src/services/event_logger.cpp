#include "event_logger.h"
#include "config/config.h"
#include <fstream>
#include <chrono>
#include <iostream>

namespace EventLogger {

void write_event_json(const std::string& event_type, const std::string& detail) {
    try {
        std::ofstream f(EVENTS_FILE, std::ios::app);
        if (f.is_open()) {
            f << "{\"event\":\"" << event_type << "\"";
            if (!detail.empty()) {
                f << ",\"detail\":\"" << detail << "\"";
            }
            auto now = std::chrono::system_clock::now();
            auto epoch = now.time_since_epoch();
            auto seconds = std::chrono::duration_cast<std::chrono::seconds>(epoch).count();
            f << ",\"timestamp\":" << seconds;
            f << "}\n";
            f.close();
        }
    } catch (...) {
        // Không crash app nếu ghi file lỗi
    }
}

void update_door_status_file(bool main_door_open, bool delivery_box_open) {
    try {
        std::ofstream f(DOOR_STATUS_FILE);
        if (f.is_open()) {
            f << "{\n";
            f << "  \"main_door\": " << (main_door_open ? "true" : "false") << ",\n";
            f << "  \"delivery_box\": " << (delivery_box_open ? "true" : "false") << "\n";
            f << "}\n";
            f.close();
        }
    } catch (...) {}
}

} // namespace EventLogger
