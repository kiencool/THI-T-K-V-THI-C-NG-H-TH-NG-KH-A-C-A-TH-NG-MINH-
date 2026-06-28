#pragma once
#include <string>

// Ghi log sự kiện và cập nhật trạng thái cửa ra file JSON
namespace EventLogger {
    void write_event_json(const std::string& event_type, const std::string& detail = "");
    void update_door_status_file(bool main_door_open, bool delivery_box_open);
}
