#include "ipc_bridge.h"
#include "config/config.h"
#include <fstream>
#include <cstdio>
#include <unistd.h>
#include <iostream>
#include <cerrno>

namespace IpcBridge {

bool remove_temp_file(const char* path) {
    if (!path) return false;
    return unlink(path) == 0 || errno == ENOENT;
}

bool write_text_file(const char* path, const std::string& data) {
    if (!path) return false;
    FILE* f = fopen(path, "w");
    if (!f) return false;
    fwrite(data.data(), 1, data.size(), f);
    fclose(f);
    return true;
}

bool create_flag_file(const char* path) {
    return write_text_file(path, "");
}

WebCommand poll_web_command() {
    std::ifstream cmd_file(WEB_COMMAND_FILE);
    if (!cmd_file.is_open()) return WebCommand::NONE;
    
    std::string cmd;
    std::getline(cmd_file, cmd);
    cmd_file.close();
    remove(WEB_COMMAND_FILE);
    
    // Trim whitespace
    if (!cmd.empty() && cmd.back() == '\r') cmd.pop_back();
    cmd.erase(cmd.find_last_not_of(" \n\r\t") + 1);
    cmd.erase(0, cmd.find_first_not_of(" \n\r\t"));
    
    if (cmd.empty()) return WebCommand::NONE;
    
    std::cout << "[WEB COMMAND] Received: [" << cmd << "]\n";
    
    if (cmd == "TRIGGER_MAIN_DOOR" || cmd == "UNLOCK_MAIN") return WebCommand::TRIGGER_MAIN_DOOR;
    if (cmd == "TRIGGER_DELIVERY_BOX" || cmd == "UNLOCK_DELIVERY") return WebCommand::TRIGGER_DELIVERY_BOX;
    if (cmd == "UNLOCK_ALL") return WebCommand::UNLOCK_ALL;
    if (cmd == "LOCK_MAIN_DOOR") return WebCommand::LOCK_MAIN_DOOR;
    if (cmd == "LOCK_DELIVERY_BOX") return WebCommand::LOCK_DELIVERY_BOX;
    if (cmd == "LOCK_ALL") return WebCommand::LOCK_ALL;
    if (cmd == "RELOAD_CARDS") return WebCommand::RELOAD_CARDS;
    
    return WebCommand::NONE;
}

} // namespace IpcBridge
