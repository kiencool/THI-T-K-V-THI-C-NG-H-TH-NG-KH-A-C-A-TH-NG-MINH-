#pragma once
#include "lvgl/lvgl.h"
#include <string>

namespace UIManager {
    void build_door_lock_ui();
    void show_notification(const char* title, const char* msg, bool is_success);
    void set_setup_status_text(const char* text);
    void reset_ui_to_default();
    void close_current_popup();
    void unlock_secret_menu();
    void notify_admin_card_scanned();
    void create_record_popup();
    void create_message_list_popup();
}
