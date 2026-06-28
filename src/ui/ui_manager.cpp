#include "ui_manager.h"
#include "config/config.h"
#include "drivers/lock_controller.h"
#include "drivers/process_manager.h"
#include "services/auth_service.h"
#include "services/delivery_service.h"
#include "services/event_logger.h"
#include "ipc/ipc_bridge.h"
#include <iostream>
#include <cstring>
#include <cstdint>
#include <string>
#include <cstdlib>
#include <ctime>
#include <cstdio>
#include <unistd.h>
#include <dirent.h>
#include <fstream>
#include <vector>

namespace UIManager {

// ==================== BIẾN TOÀN CỤC NỘI BỘ ====================
static uint8_t cam_buf[CAM_W * CAM_H * 4];
static lv_image_dsc_t cam_dsc;
static lv_obj_t* cam_img_obj = nullptr;
static lv_timer_t* cam_timer = nullptr;

enum SystemMode { MODE_TENANT, MODE_SHIPPER };
static SystemMode current_mode = MODE_TENANT;

static lv_obj_t* main_wrapper;
static lv_obj_t* left_panel;
static lv_obj_t* right_panel;
static lv_obj_t* pwd_ta;
static lv_obj_t* kb;

static lv_obj_t* screensaver_page = nullptr;
static lv_obj_t* clock_label = nullptr;
static lv_obj_t* date_label = nullptr;
static lv_timer_t* inactivity_timer = nullptr;

static lv_obj_t* active_popup = nullptr;
static lv_obj_t* video_player_layer = nullptr;
static lv_obj_t* popup_ta = nullptr;
static lv_obj_t* tenant_status_label = nullptr;
static lv_obj_t* btn_setup_card = nullptr;
static lv_obj_t* btn_setup_face = nullptr;
static lv_obj_t* btn_view_msg = nullptr;

static int auth_step = 0;
static bool is_tenant_menu = false;

// ==================== FORWARD DECLARATIONS ====================
static void user_activity_poke();
static void auto_close_notif_cb(lv_timer_t* timer);
static void create_camera_popup(const char* title_text);
static void create_auth_popup(const char* title_text);
static void cam_refresh_cb(lv_timer_t* timer);
static void update_clock_cb(lv_timer_t* timer);
static void enter_screensaver_cb(lv_timer_t* timer);
static void exit_video_player_cb(lv_event_t* e);

// ==================== SCREENSAVER ====================
static void user_activity_poke() {
    if (inactivity_timer) lv_timer_reset(inactivity_timer);
}

static void update_clock_cb(lv_timer_t* timer) {
    if (!clock_label || !date_label) return;
    time_t now = time(0);
    struct tm* ltm = localtime(&now);
    lv_label_set_text_fmt(clock_label, "%02d:%02d", ltm->tm_hour, ltm->tm_min);
    lv_label_set_text_fmt(date_label, "%02d/%02d/%04d", ltm->tm_mday, ltm->tm_mon + 1, ltm->tm_year + 1900);
}

static void enter_screensaver_cb(lv_timer_t* timer) {
    if (screensaver_page && main_wrapper) {
        lv_obj_clear_flag(screensaver_page, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(main_wrapper, LV_OBJ_FLAG_HIDDEN);
    }
}

static void exit_screensaver_cb(lv_event_t* e) {
    if (screensaver_page) {
        lv_obj_add_flag(screensaver_page, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(main_wrapper, LV_OBJ_FLAG_HIDDEN);
        user_activity_poke();
    }
}

// ==================== VIDEO PLAYER ====================
static void exit_video_player_cb(lv_event_t* e) {
    IpcBridge::remove_temp_file(FLAG_PLAY_VIDEO);
    system("pkill -9 ffplay");
    if (cam_timer) lv_timer_pause(cam_timer);
    if (video_player_layer) {
        lv_obj_del(video_player_layer);
        video_player_layer = nullptr;
    }
    active_popup = nullptr;
    cam_img_obj = nullptr;
    create_message_list_popup();
}

static void play_video_event_cb(lv_event_t* e) {
    user_activity_poke();
    lv_obj_t* obj = (lv_obj_t*)lv_event_get_target(e);
    const char* filename = lv_list_get_button_text(lv_obj_get_parent(obj), obj);
    if (filename) {
        std::string path = std::string(MESSAGES_DIR) + "/" + std::string(filename);
        if (active_popup) { close_current_popup(); }
        
        FILE* f = fopen(FLAG_PLAY_VIDEO, "w");
        if (f) { fputs(path.c_str(), f); fclose(f); }

        video_player_layer = (lv_obj_t*)lv_obj_create(lv_scr_act());
        lv_obj_set_size(video_player_layer, SCREEN_WIDTH, SCREEN_HEIGHT);
        lv_obj_set_style_bg_color(video_player_layer, lv_color_hex(0x000000), 0);
        lv_obj_set_style_border_width(video_player_layer, 0, 0);
        lv_obj_set_scrollbar_mode(video_player_layer, LV_SCROLLBAR_MODE_OFF);
        lv_obj_center(video_player_layer);

        create_camera_popup("WATCHING MESSAGE...");
        lv_obj_set_parent(active_popup, video_player_layer);
        lv_obj_set_size(active_popup, 440, 460);
        lv_obj_center(active_popup);
        lv_obj_set_size(cam_img_obj, 400, 380);
        lv_obj_align(cam_img_obj, LV_ALIGN_TOP_MID, 0, 10);

        lv_obj_t* btn_exit = (lv_obj_t*)lv_btn_create(video_player_layer);
        lv_obj_set_size(btn_exit, 160, 55);
        lv_obj_align(btn_exit, LV_ALIGN_BOTTOM_MID, 0, -15);
        lv_obj_set_style_bg_color(btn_exit, lv_palette_main(LV_PALETTE_RED), 0);
        lv_obj_t* lbl = (lv_obj_t*)lv_label_create(btn_exit);
        lv_label_set_text(lbl, LV_SYMBOL_CLOSE " EXIT PLAYER");
        lv_obj_center(lbl);
        lv_obj_add_event_cb(btn_exit, exit_video_player_cb, LV_EVENT_CLICKED, NULL);
    }
}

void create_message_list_popup() {
    user_activity_poke();
    if (active_popup != nullptr) close_current_popup();

    active_popup = (lv_obj_t*)lv_obj_create(lv_scr_act());
    lv_obj_set_size(active_popup, 600, 420);
    lv_obj_center(active_popup);
    lv_obj_set_style_shadow_width(active_popup, 40, 0);

    lv_obj_t* title = (lv_obj_t*)lv_label_create(active_popup);
    lv_label_set_text(title, LV_SYMBOL_VIDEO " RECORDED MESSAGES");
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 0);

    lv_obj_t* list = (lv_obj_t*)lv_list_create(active_popup);
    lv_obj_set_size(list, 550, 300);
    lv_obj_align(list, LV_ALIGN_CENTER, 0, 10);

    DIR* dir; struct dirent* ent;
    if ((dir = opendir(MESSAGES_DIR)) != NULL) {
        while ((ent = readdir(dir)) != NULL) {
            if (strstr(ent->d_name, ".avi")) {
                lv_obj_t* btn = (lv_obj_t*)lv_list_add_btn(list, LV_SYMBOL_PLAY, ent->d_name);
                lv_obj_add_event_cb(btn, play_video_event_cb, LV_EVENT_CLICKED, NULL);
            }
        }
        closedir(dir);
    }

    lv_obj_t* btn_close = (lv_obj_t*)lv_btn_create(active_popup);
    lv_obj_set_size(btn_close, 140, 50);
    lv_obj_align(btn_close, LV_ALIGN_BOTTOM_MID, 0, 15);
    lv_obj_set_style_bg_color(btn_close, lv_palette_main(LV_PALETTE_RED), 0);
    lv_obj_t* lbl = (lv_obj_t*)lv_label_create(btn_close);
    lv_label_set_text(lbl, "CLOSE");
    lv_obj_center(lbl);
    lv_obj_add_event_cb(btn_close, [](lv_event_t* e){ close_current_popup(); }, LV_EVENT_CLICKED, NULL);
}

// ==================== RECORDING ====================
static void stop_record_cb(lv_event_t* e) {
    IpcBridge::remove_temp_file(FLAG_RECORD_START);
    close_current_popup();
    show_notification("SUCCESS", "Video message saved!", true);
}

void create_record_popup() {
    user_activity_poke();
    IpcBridge::remove_temp_file(FLAG_RECORD_START);
    create_camera_popup("RECORDING MESSAGE...");
    lv_obj_t* dot = (lv_obj_t*)lv_obj_create(active_popup);
    lv_obj_set_size(dot, 15, 15);
    lv_obj_set_style_radius(dot, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(dot, lv_palette_main(LV_PALETTE_RED), 0);
    lv_obj_align(dot, LV_ALIGN_TOP_LEFT, 10, 10);
    lv_obj_t* btn_stop = (lv_obj_t*)lv_btn_create(active_popup);
    lv_obj_set_size(btn_stop, 180, 50);
    lv_obj_align(btn_stop, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_color(btn_stop, lv_palette_main(LV_PALETTE_RED), 0);
    lv_obj_t* lbl = (lv_obj_t*)lv_label_create(btn_stop);
    lv_label_set_text(lbl, "STOP & SAVE");
    lv_obj_center(lbl);
    lv_obj_add_event_cb(btn_stop, stop_record_cb, LV_EVENT_CLICKED, NULL);
    IpcBridge::create_flag_file(FLAG_RECORD_START);
}

// ==================== POPUP & NOTIFICATION ====================
void close_current_popup() {
    user_activity_poke();
    if (cam_timer) lv_timer_pause(cam_timer);
    if (active_popup) {
        lv_keyboard_set_textarea(kb, pwd_ta);
        lv_obj_delete_async(active_popup);
        active_popup = nullptr;
        cam_img_obj = nullptr;
        auth_step = 0;
    }
    IpcBridge::remove_temp_file(CAM_FRAME_PATH);
    IpcBridge::remove_temp_file(FLAG_RECORD_START);
    IpcBridge::remove_temp_file(FLAG_PLAY_VIDEO);
}

void unlock_secret_menu() {
    auth_step = 1;
    show_notification("AUTH SUCCESS", "Admin Access.", true);
    if (is_tenant_menu) {
        if (popup_ta) lv_obj_add_flag(popup_ta, LV_OBJ_FLAG_HIDDEN);
        if (btn_setup_card) lv_obj_clear_flag(btn_setup_card, LV_OBJ_FLAG_HIDDEN);
        if (btn_setup_face) lv_obj_clear_flag(btn_setup_face, LV_OBJ_FLAG_HIDDEN);
        if (tenant_status_label) lv_label_set_text(tenant_status_label, "Select setup option:");
    } else {
        if (popup_ta) lv_obj_add_flag(popup_ta, LV_OBJ_FLAG_HIDDEN);
        if (btn_view_msg) lv_obj_clear_flag(btn_view_msg, LV_OBJ_FLAG_HIDDEN);
        lv_obj_t* new_code_ta = (lv_obj_t*)lv_textarea_create(active_popup);
        lv_obj_set_size(new_code_ta, 240, 50);
        lv_obj_align(new_code_ta, LV_ALIGN_CENTER, 0, -50);
        lv_textarea_set_placeholder_text(new_code_ta, "New Order Code...");
        lv_keyboard_set_textarea(kb, new_code_ta);
        popup_ta = new_code_ta;
    }
}

void notify_admin_card_scanned() {
    if (active_popup != nullptr && auth_step == 0) unlock_secret_menu();
}

static void auto_close_notif_cb(lv_timer_t* timer) {
    lv_obj_t* notif = (lv_obj_t*)lv_timer_get_user_data(timer);
    if (notif) lv_obj_del_async(notif);
    lv_timer_del(timer);
}

void show_notification(const char* title, const char* msg, bool is_success) {
    user_activity_poke();
    lv_obj_t* notif = (lv_obj_t*)lv_obj_create(lv_scr_act());
    lv_obj_set_size(notif, 350, 150);
    lv_obj_align(notif, LV_ALIGN_TOP_MID, 0, 20);
    lv_color_t color = is_success ? lv_palette_main(LV_PALETTE_GREEN) : lv_palette_main(LV_PALETTE_RED);
    lv_obj_set_style_border_color(notif, color, 0);
    lv_obj_set_style_border_width(notif, 4, 0);
    lv_obj_t* t = (lv_obj_t*)lv_label_create(notif);
    lv_label_set_text(t, title);
    lv_obj_align(t, LV_ALIGN_TOP_MID, 0, 0);
    lv_obj_t* m = (lv_obj_t*)lv_label_create(notif);
    lv_label_set_text(m, msg);
    lv_obj_set_width(m, 300);
    lv_obj_set_style_text_align(m, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(m, LV_ALIGN_CENTER, 0, 10);
    lv_timer_create(auto_close_notif_cb, NOTIFICATION_DURATION_MS, notif);
}

// ==================== CAMERA ====================
static void cam_refresh_cb(lv_timer_t* timer) {
    if (!cam_img_obj) return;
    FILE* f = fopen(CAM_FRAME_PATH, "rb");
    if (f) {
        size_t read_bytes = fread(cam_buf, 1, sizeof(cam_buf), f);
        fclose(f);
        if (read_bytes == sizeof(cam_buf)) {
            lv_image_set_src(cam_img_obj, &cam_dsc);
        }
    }
}

static void create_camera_popup(const char* title_text) {
    if (active_popup != nullptr) return;
    memset(cam_buf, 0, sizeof(cam_buf));
    active_popup = (lv_obj_t*)lv_obj_create(right_panel);
    lv_obj_set_size(active_popup, 280, 340);
    lv_obj_center(active_popup);
    lv_obj_t* title = (lv_obj_t*)lv_label_create(active_popup);
    lv_label_set_text(title, title_text);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 0);
    cam_dsc.header.magic = LV_IMAGE_HEADER_MAGIC;
    cam_dsc.header.cf = LV_COLOR_FORMAT_ARGB8888;
    cam_dsc.header.w = CAM_W; cam_dsc.header.h = CAM_H;
    cam_dsc.header.stride = CAM_W * 4;
    cam_dsc.data_size = sizeof(cam_buf);
    cam_dsc.data = cam_buf;
    cam_img_obj = (lv_obj_t*)lv_image_create(active_popup);
    lv_obj_set_size(cam_img_obj, CAM_W, CAM_H);
    lv_obj_align(cam_img_obj, LV_ALIGN_TOP_MID, 0, 30);
    lv_image_set_src(cam_img_obj, &cam_dsc);
    if (!cam_timer) cam_timer = lv_timer_create(cam_refresh_cb, CAM_REFRESH_MS, NULL);
    else lv_timer_resume(cam_timer);
}

// ==================== EVENT HANDLERS ====================
static void setup_face_btn_cb(lv_event_t* e) {
    close_current_popup();
    create_camera_popup("ENROLLING FACE...");
    IpcBridge::create_flag_file(FLAG_ENROLL_FACE);
}

static void face_scan_btn_cb(lv_event_t* e) {
    if (lv_event_get_code(e) == LV_EVENT_CLICKED) {
        show_notification("CAMERA", "Scanning...", true);
        create_camera_popup("SCANNING FACE...");
        IpcBridge::create_flag_file(FLAG_SCAN_FACE);
    }
}

static void leave_msg_btn_cb(lv_event_t* e) {
    if (lv_event_get_code(e) == LV_EVENT_CLICKED) create_record_popup();
}

void set_setup_status_text(const char* text) {
    if (tenant_status_label && active_popup) lv_label_set_text(tenant_status_label, text);
}

void reset_ui_to_default() {
    user_activity_poke();
    current_mode = MODE_TENANT;
    lv_textarea_set_text(pwd_ta, "");
    lv_textarea_set_placeholder_text(pwd_ta, "Enter PIN...");
    lv_textarea_set_password_mode(pwd_ta, true);
    lv_keyboard_set_textarea(kb, pwd_ta);
    if (active_popup) { lv_obj_del_async(active_popup); active_popup = nullptr; }
}

// ==================== AUTH POPUP ====================
static void create_auth_popup(const char* title_text) {
    user_activity_poke();
    if (active_popup != nullptr) return;
    active_popup = (lv_obj_t*)lv_obj_create(right_panel);
    lv_obj_set_size(active_popup, 280, 440);
    lv_obj_align(active_popup, LV_ALIGN_CENTER, 0, 0);
    auth_step = 0;
    lv_obj_t* title = (lv_obj_t*)lv_label_create(active_popup);
    lv_label_set_text(title, title_text);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 0);
    popup_ta = (lv_obj_t*)lv_textarea_create(active_popup);
    lv_textarea_set_password_mode(popup_ta, true);
    lv_obj_set_size(popup_ta, 240, 50);
    lv_obj_align(popup_ta, LV_ALIGN_CENTER, 0, -50);
    lv_keyboard_set_textarea(kb, popup_ta);

    btn_setup_card = (lv_obj_t*)lv_btn_create(active_popup);
    lv_obj_set_size(btn_setup_card, 200, 50);
    lv_obj_align(btn_setup_card, LV_ALIGN_CENTER, 0, -40);
    lv_obj_t* lbl_card = (lv_obj_t*)lv_label_create(btn_setup_card);
    lv_label_set_text(lbl_card, "SETUP CARD");
    lv_obj_center(lbl_card);
    lv_obj_add_flag(btn_setup_card, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_event_cb(btn_setup_card, [](lv_event_t* e){ ProcessManager::rfid_mode = 1; set_setup_status_text("Scan card now..."); }, LV_EVENT_CLICKED, NULL);

    btn_setup_face = (lv_obj_t*)lv_btn_create(active_popup);
    lv_obj_set_size(btn_setup_face, 200, 50);
    lv_obj_align(btn_setup_face, LV_ALIGN_CENTER, 0, 20);
    lv_obj_set_style_bg_color(btn_setup_face, lv_palette_main(LV_PALETTE_TEAL), 0);
    lv_obj_t* lbl_face = (lv_obj_t*)lv_label_create(btn_setup_face);
    lv_label_set_text(lbl_face, "SETUP FACE");
    lv_obj_center(lbl_face);
    lv_obj_add_flag(btn_setup_face, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_event_cb(btn_setup_face, setup_face_btn_cb, LV_EVENT_CLICKED, NULL);

    tenant_status_label = (lv_obj_t*)lv_label_create(active_popup);
    lv_label_set_text(tenant_status_label, "Need Admin PIN");
    lv_obj_align(tenant_status_label, LV_ALIGN_BOTTOM_MID, 0, -60);

    btn_view_msg = (lv_obj_t*)lv_btn_create(active_popup);
    lv_obj_set_size(btn_view_msg, 200, 50);
    lv_obj_align(btn_view_msg, LV_ALIGN_CENTER, 0, 20);
    lv_obj_set_style_bg_color(btn_view_msg, lv_palette_main(LV_PALETTE_PURPLE), 0);
    lv_obj_t* lbl_msg = (lv_obj_t*)lv_label_create(btn_view_msg);
    lv_label_set_text(lbl_msg, "VIEW MESSAGES");
    lv_obj_center(lbl_msg);
    lv_obj_add_flag(btn_view_msg, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_event_cb(btn_view_msg, [](lv_event_t* e){ create_message_list_popup(); }, LV_EVENT_CLICKED, NULL);

    lv_obj_t* btn_close = (lv_obj_t*)lv_btn_create(active_popup);
    lv_obj_set_size(btn_close, 100, 45);
    lv_obj_align(btn_close, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_color(btn_close, lv_palette_main(LV_PALETTE_RED), 0);
    lv_obj_t* lbl = (lv_obj_t*)lv_label_create(btn_close);
    lv_label_set_text(lbl, "CANCEL");
    lv_obj_center(lbl);
    lv_obj_add_event_cb(btn_close, [](lv_event_t* e){ close_current_popup(); }, LV_EVENT_CLICKED, NULL);
}

// ==================== KEYBOARD HANDLER ====================
static void kb_event_cb(lv_event_t* e) {
    user_activity_poke();
    if (lv_event_get_code(e) == LV_EVENT_READY) {
        lv_obj_t* current_ta = (lv_obj_t*)lv_keyboard_get_textarea(kb);
        if (!current_ta) return;
        const char* txt = lv_textarea_get_text(current_ta);
        
        if (current_ta == pwd_ta) {
            if (current_mode == MODE_TENANT) {
                // === Xác thực PIN cư dân ===
                if (AuthService::verify_tenant_pin(txt)) {
                    show_notification("SUCCESS", "Unlocked!", true);
                    EventLogger::write_event_json("password_unlock", "MAIN DOOR");
                    LockController::trigger_main_door();
                } else {
                    show_notification("FAILED", "Invalid PIN!", false);
                }
            } else {
                // === Xác thực mã Shipper ===
                std::string creator_name;
                if (DeliveryService::verify_and_consume_code(txt, creator_name)) {
                    std::string msg = "Box Open for " + creator_name;
                    show_notification("SUCCESS", msg.c_str(), true);
                    EventLogger::write_event_json("shipper_unlock", creator_name);
                    LockController::trigger_delivery_box();
                } else {
                    show_notification("FAILED", "Wrong Code!", false);
                }
            }
            reset_ui_to_default();
        } else if (current_ta == popup_ta) {
            if (auth_step == 0) {
                // === Xác thực PIN Admin ===
                if (AuthService::verify_admin_pin(txt)) {
                    unlock_secret_menu();
                } else {
                    show_notification("DENIED", "Wrong PIN!", false);
                    lv_textarea_set_text(popup_ta, "");
                }
            } else if (auth_step == 1 && !is_tenant_menu) {
                show_notification("DEPRECATED", "Use Web to add code", false);
                reset_ui_to_default();
            }
        }
    }
}

// ==================== MAIN UI BUILDER ====================
void build_door_lock_ui() {
    lv_obj_clear_flag(lv_scr_act(), LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_color(lv_scr_act(), lv_color_hex(0x1a1a1a), 0);
    
    main_wrapper = (lv_obj_t*)lv_obj_create(lv_scr_act());
    lv_obj_set_size(main_wrapper, SCREEN_WIDTH, SCREEN_HEIGHT);
    lv_obj_center(main_wrapper);
    lv_obj_set_style_border_width(main_wrapper, 0, 0);
    lv_obj_set_style_bg_opa(main_wrapper, LV_OPA_TRANSP, 0);
    lv_obj_add_event_cb(main_wrapper, [](lv_event_t* e){ user_activity_poke(); }, LV_EVENT_CLICKED, NULL);
    
    left_panel = (lv_obj_t*)lv_obj_create(main_wrapper);
    lv_obj_set_size(left_panel, 500, SCREEN_HEIGHT); lv_obj_align(left_panel, LV_ALIGN_LEFT_MID, 0, 0);
    right_panel = (lv_obj_t*)lv_obj_create(main_wrapper);
    lv_obj_set_size(right_panel, 300, SCREEN_HEIGHT); lv_obj_align(right_panel, LV_ALIGN_RIGHT_MID, 0, 0);
    
    int btn_h = 75, sp = 15;
    const char* n[] = {"SHIPPER", "TENANT", LV_SYMBOL_SETTINGS " SETTINGS", LV_SYMBOL_VIDEO " FACE ID", LV_SYMBOL_AUDIO " VIDEO MSG"};
    lv_color_t c[] = {lv_palette_main(LV_PALETTE_ORANGE), lv_palette_main(LV_PALETTE_BLUE), lv_palette_main(LV_PALETTE_GREY), lv_palette_main(LV_PALETTE_TEAL), lv_palette_main(LV_PALETTE_PURPLE)};
    
    for (int i = 0; i < 5; i++) {
        lv_obj_t* b = (lv_obj_t*)lv_btn_create(right_panel);
        lv_obj_set_size(b, 260, btn_h);
        lv_obj_align(b, LV_ALIGN_TOP_MID, 0, sp * (i + 1) + btn_h * i);
        lv_obj_set_style_bg_color(b, c[i], 0);
        lv_obj_t* l = (lv_obj_t*)lv_label_create(b);
        lv_label_set_text(l, n[i]); lv_obj_center(l);
        if (i == 0) lv_obj_add_event_cb(b, [](lv_event_t* e){ user_activity_poke(); current_mode = MODE_SHIPPER; lv_textarea_set_placeholder_text(pwd_ta, "Order code..."); lv_textarea_set_password_mode(pwd_ta, false); lv_textarea_set_text(pwd_ta, ""); }, LV_EVENT_CLICKED, NULL);
        else if (i == 1) lv_obj_add_event_cb(b, [](lv_event_t* e){ user_activity_poke(); is_tenant_menu = true; create_auth_popup("TENANT CONFIG"); }, LV_EVENT_CLICKED, NULL);
        else if (i == 2) lv_obj_add_event_cb(b, [](lv_event_t* e){ user_activity_poke(); is_tenant_menu = false; create_auth_popup("SHIPPER CONFIG"); }, LV_EVENT_CLICKED, NULL);
        else if (i == 3) lv_obj_add_event_cb(b, face_scan_btn_cb, LV_EVENT_CLICKED, NULL);
        else if (i == 4) lv_obj_add_event_cb(b, leave_msg_btn_cb, LV_EVENT_CLICKED, NULL);
    }
    
    pwd_ta = (lv_obj_t*)lv_textarea_create(left_panel);
    lv_obj_set_size(pwd_ta, 460, 60); lv_obj_align(pwd_ta, LV_ALIGN_TOP_MID, 0, 20);
    lv_textarea_set_password_mode(pwd_ta, true);
    kb = (lv_obj_t*)lv_keyboard_create(left_panel);
    lv_keyboard_set_mode(kb, LV_KEYBOARD_MODE_NUMBER);
    lv_keyboard_set_textarea(kb, pwd_ta);
    lv_obj_set_size(kb, 460, 360); lv_obj_align(kb, LV_ALIGN_BOTTOM_MID, 0, -20);
    lv_obj_add_event_cb(kb, kb_event_cb, LV_EVENT_ALL, NULL);
    
    // Screensaver
    screensaver_page = (lv_obj_t*)lv_obj_create(lv_scr_act());
    lv_obj_set_size(screensaver_page, SCREEN_WIDTH, SCREEN_HEIGHT);
    lv_obj_set_style_bg_color(screensaver_page, lv_color_hex(0x000000), 0);
    lv_obj_add_flag(screensaver_page, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_event_cb(screensaver_page, exit_screensaver_cb, LV_EVENT_CLICKED, NULL);
    clock_label = (lv_obj_t*)lv_label_create(screensaver_page);
    lv_obj_set_style_text_font(clock_label, &lv_font_montserrat_24, 0);
    lv_obj_set_style_transform_scale(clock_label, 512, 0);
    lv_obj_set_style_text_color(clock_label, lv_palette_main(LV_PALETTE_TEAL), 0);
    lv_obj_align(clock_label, LV_ALIGN_CENTER, 0, -20);
    date_label = (lv_obj_t*)lv_label_create(screensaver_page);
    lv_obj_set_style_text_color(date_label, lv_palette_main(LV_PALETTE_GREY), 0);
    lv_obj_align(date_label, LV_ALIGN_CENTER, 0, 40);
    lv_timer_create(update_clock_cb, 1000, NULL);
    inactivity_timer = lv_timer_create(enter_screensaver_cb, SCREENSAVER_TIMEOUT_MS, NULL);
}

} // namespace UIManager
