#pragma once
#include <string>
#include <atomic>
#include <mutex>

namespace ProcessManager {
    // Shared state (thread-safe)
    extern std::atomic<bool> card_event;
    extern std::atomic<bool> face_event;
    extern std::atomic<bool> face_enroll_event;
    
    // Thread-safe getters for string data
    std::string get_scanned_uid();
    std::string get_recognized_face_name();
    std::string get_enroll_status();
    
    // RFID mode: 0=normal, 1=card-enroll
    extern std::atomic<int> rfid_mode;
    
    // Background tasks
    void rfid_task();
    void face_task();
    void sensor_task();
    
    // Start Python web services
    void start_web_services();
}
