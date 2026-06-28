#ifndef UI_APP_H
#define UI_APP_H

#include "lvgl/lvgl.h"
#include <string>

// --- Các hàm Giao diện gọi từ main.cpp ---
void build_door_lock_ui();
void show_notification(const char * title, const char * msg, bool is_success);
void set_setup_status_text(const char* text);
void reset_ui_to_default();
void create_record_popup();
void stop_recording();
void create_message_list_popup();
// --- Các hàm xử lý sự kiện gọi từ main.cpp ---
void close_current_popup();
void unlock_secret_menu();
void notify_admin_card_scanned();

// --- Các hàm và biến liên kết với phần cứng (External) ---
extern void trigger_main_door();      
extern void trigger_delivery_box();   
extern void write_event_json(const std::string& event_type, const std::string& event_detail);
extern int rfid_mode; 

#endif
