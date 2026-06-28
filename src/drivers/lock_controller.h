#pragma once
#include <string>
#include <atomic>

namespace LockController {
    // Sensor states (written by sensor_task, read by trigger_lock)
    extern std::atomic<bool> main_door_open;
    extern std::atomic<bool> delivery_box_open;
    
    // Cancel flags for lock wait loops
    extern std::atomic<bool> cancel_main_door_wait;
    extern std::atomic<bool> cancel_delivery_box_wait;
    
    void trigger_main_door();
    void trigger_delivery_box();
    void reset_all_locks();
}
