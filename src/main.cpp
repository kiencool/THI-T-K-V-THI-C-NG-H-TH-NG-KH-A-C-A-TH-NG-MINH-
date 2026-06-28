#include "lvgl/lvgl.h"
#include "ui/ui_app.h"
#include <unistd.h>
#include <iostream>
#include <fstream>
#include <thread>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <mutex>
#include <signal.h>
#include <fcntl.h>
#include <SDL2/SDL.h>
#include <vector>
#include <sstream>
#include <mutex>
#include <ctime>
int rfid_mode = 0; 
std::atomic<bool> card_event(false);
std::string scanned_uid = "";
std::atomic<bool> face_event(false);
std::string recognized_face_name = "";

struct Card {
    std::string uid;
    std::string time_added;
};
std::vector<Card> registered_cards;
std::mutex cards_mutex;

std::string my_admin_card = "76 19 75 A6 BC"; // Thẻ mở Setting
std::atomic<bool> face_enroll_event(false);
std::string enroll_status = "";

// === SENSOR STATE ===
std::atomic<bool> main_door_open(false);
std::atomic<bool> delivery_box_open(false);

// === WEB DASHBOARD EVENT BRIDGE ===
// Ghi structured event vào file JSON để server.py đọc và push qua WebSocket
static const char* EVENTS_FILE = "/tmp/smart_door_events.json";

// === DATABASE ===
void load_registered_cards() {
    std::lock_guard<std::mutex> lock(cards_mutex);
    registered_cards.clear();
    std::ifstream f("../rfid_cards.txt");
    if (f.is_open()) {
        std::string line;
        while (std::getline(f, line)) {
            size_t delim = line.find('|');
            if (delim != std::string::npos) {
                Card c;
                c.uid = line.substr(0, delim);
                c.time_added = line.substr(delim + 1);
                c.uid.erase(c.uid.find_last_not_of(" \n\r\t") + 1);
                c.time_added.erase(c.time_added.find_last_not_of(" \n\r\t") + 1);
                registered_cards.push_back(c);
            }
        }
        f.close();
    }
    std::cout << "[SYSTEM] Loaded " << registered_cards.size() << " cards from DB.\n";
}

void write_event_json(const std::string &event_type, const std::string &detail = "") {
    try {
        std::ofstream f(EVENTS_FILE, std::ios::app);
        if (f.is_open()) {
            f << "{\"event\":\"" << event_type << "\"";
            if (!detail.empty()) {
                f << ",\"detail\":\"" << detail << "\"";
            }
            // Thêm timestamp đơn giản
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

void update_door_status_file() {
    try {
        std::ofstream f("/tmp/door_status.json");
        if (f.is_open()) {
            f << "{\n";
            f << "  \"main_door\": " << (main_door_open ? "true" : "false") << ",\n";
            f << "  \"delivery_box\": " << (delivery_box_open ? "true" : "false") << "\n";
            f << "}\n";
            f.close();
        }
    } catch (...) {}
}

// === GPIO LOCK CONFIGURATION ===
static const int MAIN_DOOR_GPIO = 26;          // Khóa cổng chính
static const int DELIVERY_BOX_GPIO = 27;       // Khóa thùng đồ Shipper
static const bool MAIN_DOOR_ACTIVE_HIGH = false;   // MAIN DOOR active-low: 0 = mở, 1 = đóng
static const bool DELIVERY_BOX_ACTIVE_HIGH = false;  // DELIVERY BOX active-low: 0 = mở, 1 = đóng
static const int LOCK_PULSE_SECONDS = 5;

// === RELAY CONTROL SAFETY ===
std::mutex relay_mutex;  // Chỉ cho một relay bật lúc một
std::atomic<bool> relay_in_use(false);
// === GPIO CONTROL via posix_spawn (tránh system()/fork() gây nhấp nháy DRM) ===
#include <spawn.h>
#include <sys/wait.h>
extern char **environ;

static bool run_shell_command(const std::string &cmd, const char *name, const char *phase) {
    std::cout << "[GPIO] " << phase << " " << name << ": " << cmd << "\n";
    
    pid_t pid;
    const char *argv[] = {"/bin/sh", "-c", cmd.c_str(), NULL};
    
    posix_spawn_file_actions_t actions;
    posix_spawn_file_actions_init(&actions);
    
    // Redirect stdout/stderr to /dev/null để tránh ảnh hưởng terminal
    posix_spawn_file_actions_addopen(&actions, STDOUT_FILENO, "/dev/null", O_WRONLY, 0);
    posix_spawn_file_actions_addopen(&actions, STDERR_FILENO, "/dev/null", O_WRONLY, 0);
    
    int ret = posix_spawn(&pid, "/bin/sh", &actions, NULL, (char *const *)argv, environ);
    posix_spawn_file_actions_destroy(&actions);
    
    if (ret != 0) {
        std::cerr << "[GPIO] ERROR " << phase << " " << name << " (spawn failed: " << ret << ")\n";
        return false;
    }
    
    int status;
    waitpid(pid, &status, 0);
    
    if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
        return true;
    }
    std::cerr << "[GPIO] ERROR " << phase << " " << name << " (return=" << WEXITSTATUS(status) << ")\n";
    return false;
}

static bool release_gpio_pin(int gpio, const char *name, const char *phase) {
    std::string cmd_gpio = std::string("gpio -g mode ") + std::to_string(gpio) + " in";
    if (run_shell_command(cmd_gpio, name, phase)) return true;

    std::string cmd_raspi = std::string("raspi-gpio set ") + std::to_string(gpio) + " ip";
    if (run_shell_command(cmd_raspi, name, phase)) return true;

    return false;
}

static bool set_lock_state(int gpio, const char *name, bool active, bool active_high, const char *phase) {
    // active_high == true: 1 = active, 0 = inactive
    // active_high == false: 0 = active, 1 = inactive
    const char *logic = (active ? (active_high ? "dh" : "dl") : (active_high ? "dl" : "dh"));
    const char *value = (std::string(logic) == "dh") ? "1" : "0";

    std::string cmd_gpio = std::string("gpio -g mode ") + std::to_string(gpio) + " out && gpio -g write " + std::to_string(gpio) + " " + value;
    if (run_shell_command(cmd_gpio, name, phase)) return true;

    std::string cmd_raspi = std::string("raspi-gpio set ") + std::to_string(gpio) + " op " + logic;
    if (run_shell_command(cmd_raspi, name, phase)) return true;

    std::string cmd_pinctrl = std::string("pinctrl set ") + std::to_string(gpio) + " op pn " + logic;
    return run_shell_command(cmd_pinctrl, name, phase);
}

static void reset_lock(int gpio, const char *name, bool active_high) {
    if (!set_lock_state(gpio, name, false, active_high, "RESET")) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        set_lock_state(gpio, name, false, active_high, "RESET-RETRY");
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    release_gpio_pin(gpio, name, "RELEASE");
}

static void reset_all_locks() {
    std::cout << "[GPIO] RESET ALL LOCKS: MAIN_DOOR_ACTIVE_HIGH=" << (MAIN_DOOR_ACTIVE_HIGH ? "true" : "false")
              << ", DELIVERY_BOX_ACTIVE_HIGH=" << (DELIVERY_BOX_ACTIVE_HIGH ? "true" : "false") << "\n";
    reset_lock(MAIN_DOOR_GPIO, "MAIN DOOR", MAIN_DOOR_ACTIVE_HIGH);
    reset_lock(DELIVERY_BOX_GPIO, "DELIVERY BOX", DELIVERY_BOX_ACTIVE_HIGH);
}

std::atomic<bool> cancel_main_door_wait(false);
std::atomic<bool> cancel_delivery_box_wait(false);

void trigger_lock(int gpio, const char* name, bool active_high, int duration_sec) {
    std::thread([gpio, name, active_high, duration_sec]() {
        {
            std::lock_guard<std::mutex> lock(relay_mutex);
            std::cout << "[GPIO] Activating " << name << " (GPIO " << gpio << ")...\n";
            write_event_json("door_unlock", std::string(name) + ",gpio=" + std::to_string(gpio));
            if (!set_lock_state(gpio, name, true, active_high, "ACTIVATE")) {
                std::cerr << "[GPIO] WARNING " << name << " may not have activated correctly.\n";
            }
        }

        // Chờ cửa mở ra
        std::cout << "[GPIO] Waiting for " << name << " to open...\n";
        while (true) {
            if ((gpio == MAIN_DOOR_GPIO && cancel_main_door_wait) || 
                (gpio == DELIVERY_BOX_GPIO && cancel_delivery_box_wait)) {
                std::cout << "[GPIO] Canceled wait for " << name << "\n";
                break;
            }
            if ((gpio == MAIN_DOOR_GPIO && main_door_open) || 
                (gpio == DELIVERY_BOX_GPIO && delivery_box_open)) {
                break; // Cửa đã mở
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }

        // Cửa đã mở, giờ chờ cửa đóng lại
        std::cout << "[GPIO] Waiting for " << name << " to close...\n";
        while (true) {
            if ((gpio == MAIN_DOOR_GPIO && cancel_main_door_wait) || 
                (gpio == DELIVERY_BOX_GPIO && cancel_delivery_box_wait)) {
                break;
            }
            if ((gpio == MAIN_DOOR_GPIO && !main_door_open) || 
                (gpio == DELIVERY_BOX_GPIO && !delivery_box_open)) {
                break; // Cửa đã đóng
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        
        if ((gpio == MAIN_DOOR_GPIO && cancel_main_door_wait) || 
            (gpio == DELIVERY_BOX_GPIO && cancel_delivery_box_wait)) {
            // Cancelled, reset flag
            if (gpio == MAIN_DOOR_GPIO) cancel_main_door_wait = false;
            if (gpio == DELIVERY_BOX_GPIO) cancel_delivery_box_wait = false;
        } else {
            // Thêm độ trễ nhỏ để đảm bảo chốt cửa ăn khớp
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
        }

        {
            std::lock_guard<std::mutex> lock(relay_mutex);
            // === DEACTIVATION: Nhả mềm để giảm back-EMF gây sụt áp ===
            std::cout << "[GPIO] Soft-releasing " << name << "...\n";
            release_gpio_pin(gpio, name, "SOFT-RELEASE");
            
            // Bước 2: Chờ 200ms cho điện áp ổn định sau khi relay chuyển trạng thái
            std::this_thread::sleep_for(std::chrono::milliseconds(200));

            std::cout << "[GPIO] " << name << " deactivated.\n";
            write_event_json("door_lock", std::string(name));
        }
    }).detach();
}

void trigger_main_door() {
    trigger_lock(MAIN_DOOR_GPIO, "MAIN DOOR", MAIN_DOOR_ACTIVE_HIGH, LOCK_PULSE_SECONDS);
}

void trigger_delivery_box() {
    trigger_lock(DELIVERY_BOX_GPIO, "DELIVERY BOX", DELIVERY_BOX_ACTIVE_HIGH, LOCK_PULSE_SECONDS);
}
/* -------------------------------------------------------------------------- */
/* LUỒNG RFID: Khởi động Driver Python (Có cơ chế chống Zombie Process)       */
/* -------------------------------------------------------------------------- */
void rfid_task() {
    std::cout << "[RFID] Don dep cac tien trinh cu...\n";
    // 1. Tiêu diệt tất cả rfid_driver.py đang chạy ngầm từ lần trước
    system("sudo pkill -f rfid_driver.py");
    usleep(200000); // Chờ 0.2 giây để hệ điều hành nhả cổng SPI ra

    std::cout << "[RFID] Khoi dong Driver giao tiep phan cung...\n";
    
    // 2. Mở tiến trình Python mới
    FILE *pipe = popen("python3 ../rfid_driver.py", "r"); 
    if (!pipe) {
        std::cerr << "[RFID] LOI: Khong the khoi dong Python Driver!\n";
        return;
    }

    char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        std::string line(buffer);
        line.erase(line.find_last_not_of(" \n\r\t") + 1);

        if (line.rfind("SCAN:", 0) == 0) { 
            scanned_uid = line.substr(5); 
            card_event = true;
        }
    }
    
    // Đóng pipe khi kết thúc
    pclose(pipe);
}
/* -------------------------------------------------------------------------- */
/* LUỒNG FACE AI: Đọc tín hiệu từ Camera Driver                               */
/* -------------------------------------------------------------------------- */
void face_task() {
    std::cout << "[FACE] Don dep tien trinh camera cu...\n";
    system("sudo pkill -f face_driver.py");
    usleep(200000); 

    std::cout << "[FACE] Khoi dong AI Camera...\n";
    FILE *pipe = popen("python3 ../face_driver.py", "r"); 
    if (!pipe) {
        std::cerr << "[FACE] LOI: Khong the khoi dong Camera Driver!\n";
        return;
    }

	char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        std::string line(buffer);
        line.erase(line.find_last_not_of(" \n\r\t") + 1);

        // Bắt tín hiệu mở khóa
        if (line.rfind("FACE:", 0) == 0) { 
            recognized_face_name = line.substr(5); 
            face_event = true;
        }
        // Bắt tín hiệu Đăng ký khuôn mặt mới
        else if (line.rfind("ENROLL:", 0) == 0) {
            enroll_status = line.substr(7);
            face_enroll_event = true;
        }
    }
    pclose(pipe);
}

/* -------------------------------------------------------------------------- */
/* LUỒNG SENSOR: Đọc tín hiệu từ cảm biến từ                                  */
/* -------------------------------------------------------------------------- */
void sensor_task() {
    std::cout << "[SENSOR] Don dep tien trinh cu...\n";
    system("sudo pkill -f sensor_driver.py");
    usleep(200000); 

    std::cout << "[SENSOR] Khoi dong Driver...\n";
    FILE *pipe = popen("python3 ../sensor_driver.py", "r"); 
    if (!pipe) {
        std::cerr << "[SENSOR] LOI: Khong the khoi dong Sensor Driver!\n";
        return;
    }

	char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        std::string line(buffer);
        line.erase(line.find_last_not_of(" \n\r\t") + 1);

        if (line.rfind("SENSOR:MAIN_DOOR:", 0) == 0) { 
            std::string state = line.substr(17);
            bool is_open = (state == "OPEN");
            if (is_open != main_door_open) {
                main_door_open = is_open;
                write_event_json(is_open ? "physical_door_open" : "physical_door_close", "MAIN DOOR");
                update_door_status_file();
            }
        }
        else if (line.rfind("SENSOR:DELIVERY_BOX:", 0) == 0) {
            std::string state = line.substr(20);
            bool is_open = (state == "OPEN");
            if (is_open != delivery_box_open) {
                delivery_box_open = is_open;
                write_event_json(is_open ? "physical_door_open" : "physical_door_close", "DELIVERY BOX");
                update_door_status_file();
            }
        }
    }
    pclose(pipe);
}
static void cleanup_signal_handler(int sig) {
    std::cout << "[GPIO] SIGNAL " << sig << " received, resetting locks...\n";
    reset_all_locks();
    exit(0);
}

int main(void) {
    std::cout << "[SYSTEM] Starting Python Services from C++...\n";
    system("pkill -f server_final_fix.py");
    system("pkill -f event_bridge.py");
    system("sudo -u lckien nohup python3 ../server_final_fix.py > ../web_server.log 2>&1 &");
    system("sudo -u lckien nohup python3 ../event_bridge.py > ../event_bridge.log 2>&1 &");

    lv_init();
    load_registered_cards();
    reset_all_locks();
    signal(SIGINT, cleanup_signal_handler);
    signal(SIGTERM, cleanup_signal_handler);
    signal(SIGABRT, cleanup_signal_handler);

    lv_display_t * disp = lv_sdl_window_create(800, 480);

	// Đoạn code KIOSK MODE trong main.cpp sửa thành:
    SDL_Window * window = (SDL_Window *)lv_sdl_window_get_window(disp);
    
    // Ép màn hình hiển thị bằng đúng độ phân giải 800x480 rồi phóng to
    SDL_SetWindowFullscreen(window, SDL_WINDOW_FULLSCREEN_DESKTOP);
    //SDL_ShowCursor(SDL_DISABLE);

    // --- KẾT THÚC ---

    lv_indev_t * mouse = lv_sdl_mouse_create();
    lv_indev_t * keyboard = lv_sdl_keyboard_create();

    build_door_lock_ui(); 

    // Chạy Thread RFID
    std::thread rfid_thread(rfid_task);
    rfid_thread.detach(); 

    // Chạy Thread Camera
    std::thread face_thread(face_task);
    face_thread.detach();

    // Chạy Thread Sensor
    std::thread sensor_thread(sensor_task);
    sensor_thread.detach();

    auto setup_start_time = std::chrono::steady_clock::now();
    bool is_setup_timer_running = false;

    while(1) {
        lv_timer_handler();
        
        const Uint8 *state = SDL_GetKeyboardState(NULL);
        if (state[SDL_SCANCODE_ESCAPE]) {
            std::cout << "[SYSTEM] ESC pressed. Exiting application...\n";
            break;
        }

        
        // ---------------- ĐỌC LỆNH TỪ WEB DASHBOARD ----------------
        std::ifstream cmd_file("/tmp/web_command.txt");
        if (cmd_file.is_open()) {
            std::string cmd;
            std::getline(cmd_file, cmd);
            cmd_file.close();
            remove("/tmp/web_command.txt");
            
            if (!cmd.empty() && cmd.back() == '\r') cmd.pop_back();
            cmd.erase(cmd.find_last_not_of(" \n\r\t") + 1);
            cmd.erase(0, cmd.find_first_not_of(" \n\r\t"));
            
            if (!cmd.empty()) {
                std::cout << "[WEB COMMAND] Received: [" << cmd << "]\n";
            }
            
            if (cmd == "TRIGGER_MAIN_DOOR" || cmd == "UNLOCK_MAIN") {
                cancel_main_door_wait = false;
                trigger_main_door();
            } else if (cmd == "TRIGGER_DELIVERY_BOX" || cmd == "UNLOCK_DELIVERY") {
                cancel_delivery_box_wait = false;
                trigger_delivery_box();
            } else if (cmd == "UNLOCK_ALL") {
                cancel_main_door_wait = false;
                cancel_delivery_box_wait = false;
                trigger_main_door();
                std::this_thread::sleep_for(std::chrono::milliseconds(200));
                trigger_delivery_box();
            } else if (cmd == "LOCK_MAIN_DOOR") {
                cancel_main_door_wait = true;
                release_gpio_pin(MAIN_DOOR_GPIO, "MAIN DOOR", "WEB_LOCK");
                write_event_json("door_lock", "MAIN DOOR");
            } else if (cmd == "LOCK_DELIVERY_BOX") {
                cancel_delivery_box_wait = true;
                release_gpio_pin(DELIVERY_BOX_GPIO, "DELIVERY BOX", "WEB_LOCK");
                write_event_json("door_lock", "DELIVERY BOX");
            } else if (cmd == "LOCK_ALL") {
                cancel_main_door_wait = true;
                cancel_delivery_box_wait = true;
                release_gpio_pin(MAIN_DOOR_GPIO, "MAIN DOOR", "WEB_LOCK");
                release_gpio_pin(DELIVERY_BOX_GPIO, "DELIVERY BOX", "WEB_LOCK");
                write_event_json("door_lock", "MAIN DOOR");
                write_event_json("door_lock", "DELIVERY BOX");
            } else if (cmd == "RELOAD_CARDS") {
                load_registered_cards();
            }
        }

        // 1. LOGIC 5 GIÂY CHO TENANT
        if (rfid_mode == 1) {
            if (!is_setup_timer_running) {
                setup_start_time = std::chrono::steady_clock::now();
                is_setup_timer_running = true;
            } else {
                auto now = std::chrono::steady_clock::now();
                if (std::chrono::duration_cast<std::chrono::seconds>(now - setup_start_time).count() >= 5) {
                    rfid_mode = 0; 
                    is_setup_timer_running = false;
                    set_setup_status_text("Timeout! Try again.");
                }
            }
        } else {
            is_setup_timer_running = false; 
        }
// ---------------- XỬ LÝ SỰ KIỆN KHUÔN MẶT ----------------
        if (face_event) {
            face_event = false;
            close_current_popup();
            if (recognized_face_name == "TIMEOUT") {
                show_notification("FACE ID FAILED", "No registered face found.", false);
            } else {
                std::string msg = "Welcome back, " + recognized_face_name + "!";
                show_notification("FACE RECOGNIZED", msg.c_str(), true);
                write_event_json("face_recognized", recognized_face_name);
                trigger_main_door();
            }
        }
        // ---------------- XỬ LÝ SỰ KIỆN ĐĂNG KÝ KHUÔN MẶT ----------------
        if (face_enroll_event) {
            face_enroll_event = false;
            close_current_popup();
            if (enroll_status == "SUCCESS") {
                show_notification("ENROLL SUCCESS", "Tenant face registered!", true);
                set_setup_status_text("Face Saved!");
            } else {
                show_notification("ENROLL FAILED", "No face detected. Try again.", false);
                set_setup_status_text("Enroll Failed!");
            }
        }
	// Trong main.cpp
	if (card_event) {
		card_event = false;
		
        // ƯU TIÊN 1: Nếu đang trong 5s cài đặt thẻ
        if (rfid_mode == 1) {
            // Lấy thời gian hiện tại
            std::time_t t = std::time(nullptr);
            char time_str[100];
            std::strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", std::localtime(&t));

            // Lưu vào file
            std::ofstream f("../rfid_cards.txt", std::ios::app);
            if (f.is_open()) {
                f << scanned_uid << "|" << time_str << "\n";
                f.close();
            }
            load_registered_cards(); // Tải lại vào RAM
            
			rfid_mode = 0; 
			set_setup_status_text("Card Saved!");
			write_event_json("rfid_enrolled", scanned_uid);
		} 
		// ƯU TIÊN 2: Kiểm tra thẻ mở cửa
		else {
            bool found = false;
            std::string user_time = "";
            
            cards_mutex.lock();
            for (const auto& c : registered_cards) {
                if (c.uid == scanned_uid) {
                    found = true;
                    user_time = c.time_added;
                    break;
                }
            }
            cards_mutex.unlock();

			if (found) {
                std::string msg = "Access Granted";
				show_notification("ACCESS GRANTED", msg.c_str(), true);
				write_event_json("rfid_scan", scanned_uid + ",matched=true,time=" + user_time);
				trigger_main_door();
			} 
			else if (scanned_uid == my_admin_card) {
				notify_admin_card_scanned(); // Mở khóa menu settings/tenant
			} 
			else {
				write_event_json("rfid_scan", scanned_uid + ",matched=false");
				show_notification("ACCESS DENIED", "Unknown Card!", false);
			}
		}
	}

        usleep(5000); 
    }
    return 0;
}
