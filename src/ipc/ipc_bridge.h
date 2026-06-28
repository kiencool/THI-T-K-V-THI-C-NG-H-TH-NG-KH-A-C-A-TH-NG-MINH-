#pragma once
#include <string>

namespace IpcBridge {
    // File utility helpers
    bool remove_temp_file(const char* path);
    bool create_flag_file(const char* path);
    bool write_text_file(const char* path, const std::string& data);
    
    // Web command processing
    enum class WebCommand {
        NONE,
        TRIGGER_MAIN_DOOR,
        TRIGGER_DELIVERY_BOX,
        UNLOCK_ALL,
        LOCK_MAIN_DOOR,
        LOCK_DELIVERY_BOX,
        LOCK_ALL,
        RELOAD_CARDS
    };
    
    WebCommand poll_web_command();
}
