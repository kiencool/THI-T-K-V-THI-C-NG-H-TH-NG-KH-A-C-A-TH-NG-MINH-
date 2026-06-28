// ===========================================================================
// Smart Door Pi — Entry Point
// Refactored: Clean Architecture with layered modules
// ===========================================================================
#include "lvgl/lvgl.h"
#include "config/config.h"
#include "ui/ui_manager.h"
#include "drivers/lock_controller.h"
#include "drivers/process_manager.h"
#include "services/auth_service.h"
#include "services/event_logger.h"
#include "ipc/ipc_bridge.h"

#include <unistd.h>
#include <iostream>
#include <thread>
#include <chrono>
#include <signal.h>
#include <SDL2/SDL.h>

// === Signal Handler ===
static void cleanup_signal_handler(int sig) {
    std::cout << "[GPIO] SIGNAL " << sig << " received, resetting locks...\n";
    LockController::reset_all_locks();
    exit(0);
}

int main(void) {
    // 1. Khởi động Web Services
    ProcessManager::start_web_services();

    // 2. Khởi tạo LVGL
    lv_init();
    AuthService::load_registered_cards();
    LockController::reset_all_locks();

    // 3. Đăng ký signal handler
    signal(SIGINT, cleanup_signal_handler);
    signal(SIGTERM, cleanup_signal_handler);
    signal(SIGABRT, cleanup_signal_handler);

    // 4. Tạo cửa sổ hiển thị SDL2 (Kiosk Mode)
    lv_display_t* disp = lv_sdl_window_create(SCREEN_WIDTH, SCREEN_HEIGHT);
    SDL_Window* window = (SDL_Window*)lv_sdl_window_get_window(disp);
    SDL_SetWindowFullscreen(window, SDL_WINDOW_FULLSCREEN_DESKTOP);

    lv_indev_t* mouse = lv_sdl_mouse_create();
    lv_indev_t* keyboard = lv_sdl_keyboard_create();

    // 5. Xây dựng giao diện
    UIManager::build_door_lock_ui();

    // 6. Khởi chạy các luồng Driver
    std::thread rfid_thread(ProcessManager::rfid_task);
    rfid_thread.detach();
    std::thread face_thread(ProcessManager::face_task);
    face_thread.detach();
    std::thread sensor_thread(ProcessManager::sensor_task);
    sensor_thread.detach();

    // 7. Timer cho chế độ enroll RFID (5 giây timeout)
    auto setup_start_time = std::chrono::steady_clock::now();
    bool is_setup_timer_running = false;

    // ==================== MAIN EVENT LOOP ====================
    while (1) {
        lv_timer_handler();

        // ESC để thoát
        const Uint8* state = SDL_GetKeyboardState(NULL);
        if (state[SDL_SCANCODE_ESCAPE]) {
            std::cout << "[SYSTEM] ESC pressed. Exiting application...\n";
            break;
        }

        // --- Xử lý lệnh từ Web Dashboard ---
        IpcBridge::WebCommand web_cmd = IpcBridge::poll_web_command();
        switch (web_cmd) {
            case IpcBridge::WebCommand::TRIGGER_MAIN_DOOR:
                LockController::cancel_main_door_wait = false;
                LockController::trigger_main_door();
                break;
            case IpcBridge::WebCommand::TRIGGER_DELIVERY_BOX:
                LockController::cancel_delivery_box_wait = false;
                LockController::trigger_delivery_box();
                break;
            case IpcBridge::WebCommand::UNLOCK_ALL:
                LockController::cancel_main_door_wait = false;
                LockController::cancel_delivery_box_wait = false;
                LockController::trigger_main_door();
                std::this_thread::sleep_for(std::chrono::milliseconds(200));
                LockController::trigger_delivery_box();
                break;
            case IpcBridge::WebCommand::LOCK_MAIN_DOOR:
                LockController::cancel_main_door_wait = true;
                EventLogger::write_event_json("door_lock", "MAIN DOOR");
                break;
            case IpcBridge::WebCommand::LOCK_DELIVERY_BOX:
                LockController::cancel_delivery_box_wait = true;
                EventLogger::write_event_json("door_lock", "DELIVERY BOX");
                break;
            case IpcBridge::WebCommand::LOCK_ALL:
                LockController::cancel_main_door_wait = true;
                LockController::cancel_delivery_box_wait = true;
                EventLogger::write_event_json("door_lock", "MAIN DOOR");
                EventLogger::write_event_json("door_lock", "DELIVERY BOX");
                break;
            case IpcBridge::WebCommand::RELOAD_CARDS:
                AuthService::load_registered_cards();
                break;
            default: break;
        }

        // --- RFID Enroll Timer (5s timeout) ---
        if (ProcessManager::rfid_mode == 1) {
            if (!is_setup_timer_running) {
                setup_start_time = std::chrono::steady_clock::now();
                is_setup_timer_running = true;
            } else {
                auto now = std::chrono::steady_clock::now();
                if (std::chrono::duration_cast<std::chrono::seconds>(now - setup_start_time).count() >= RFID_ENROLL_TIMEOUT_SEC) {
                    ProcessManager::rfid_mode = 0;
                    is_setup_timer_running = false;
                    UIManager::set_setup_status_text("Timeout! Try again.");
                }
            }
        } else {
            is_setup_timer_running = false;
        }

        // --- Xử lý sự kiện khuôn mặt ---
        if (ProcessManager::face_event) {
            ProcessManager::face_event = false;
            UIManager::close_current_popup();
            std::string face_name = ProcessManager::get_recognized_face_name();
            if (face_name == "TIMEOUT") {
                UIManager::show_notification("FACE ID FAILED", "No registered face found.", false);
            } else {
                std::string msg = "Welcome back, " + face_name + "!";
                UIManager::show_notification("FACE RECOGNIZED", msg.c_str(), true);
                EventLogger::write_event_json("face_recognized", face_name);
                LockController::trigger_main_door();
            }
        }

        // --- Xử lý sự kiện đăng ký khuôn mặt ---
        if (ProcessManager::face_enroll_event) {
            ProcessManager::face_enroll_event = false;
            UIManager::close_current_popup();
            std::string status = ProcessManager::get_enroll_status();
            if (status == "SUCCESS") {
                UIManager::show_notification("ENROLL SUCCESS", "Tenant face registered!", true);
                UIManager::set_setup_status_text("Face Saved!");
            } else {
                UIManager::show_notification("ENROLL FAILED", "No face detected. Try again.", false);
                UIManager::set_setup_status_text("Enroll Failed!");
            }
        }

        // --- Xử lý sự kiện quét thẻ RFID ---
        if (ProcessManager::card_event) {
            ProcessManager::card_event = false;
            std::string uid = ProcessManager::get_scanned_uid();
            
            if (ProcessManager::rfid_mode == 1) {
                // Chế độ đăng ký thẻ mới
                AuthService::enroll_card(uid);
                ProcessManager::rfid_mode = 0;
                UIManager::set_setup_status_text("Card Saved!");
                EventLogger::write_event_json("rfid_enrolled", uid);
            } else {
                // Chế độ xác thực thẻ
                std::string user_time;
                if (AuthService::find_card(uid, user_time)) {
                    UIManager::show_notification("ACCESS GRANTED", "Access Granted", true);
                    EventLogger::write_event_json("rfid_scan", uid + ",matched=true,time=" + user_time);
                    LockController::trigger_main_door();
                } else if (AuthService::is_admin_card(uid)) {
                    UIManager::notify_admin_card_scanned();
                } else {
                    EventLogger::write_event_json("rfid_scan", uid + ",matched=false");
                    UIManager::show_notification("ACCESS DENIED", "Unknown Card!", false);
                }
            }
        }

        usleep(MAIN_LOOP_SLEEP_US);
    }
    return 0;
}
