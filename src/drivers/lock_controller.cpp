#include "lock_controller.h"
#include "config/config.h"
#include "services/event_logger.h"
#include <iostream>
#include <thread>
#include <mutex>
#include <chrono>
#include <cstring>
#include <unistd.h>
#include <fcntl.h>
#include <spawn.h>
#include <sys/wait.h>

extern char **environ;

namespace LockController {

std::atomic<bool> main_door_open(false);
std::atomic<bool> delivery_box_open(false);
std::atomic<bool> cancel_main_door_wait(false);
std::atomic<bool> cancel_delivery_box_wait(false);

static std::mutex relay_mutex;

static bool run_shell_command(const std::string& cmd, const char* name, const char* phase) {
    std::cout << "[GPIO] " << phase << " " << name << ": " << cmd << "\n";
    pid_t pid;
    const char* argv[] = {"/bin/sh", "-c", cmd.c_str(), NULL};
    posix_spawn_file_actions_t actions;
    posix_spawn_file_actions_init(&actions);
    posix_spawn_file_actions_addopen(&actions, STDOUT_FILENO, "/dev/null", O_WRONLY, 0);
    posix_spawn_file_actions_addopen(&actions, STDERR_FILENO, "/dev/null", O_WRONLY, 0);
    int ret = posix_spawn(&pid, "/bin/sh", &actions, NULL, (char* const*)argv, environ);
    posix_spawn_file_actions_destroy(&actions);
    if (ret != 0) {
        std::cerr << "[GPIO] ERROR " << phase << " " << name << " (spawn failed: " << ret << ")\n";
        return false;
    }
    int status;
    waitpid(pid, &status, 0);
    if (WIFEXITED(status) && WEXITSTATUS(status) == 0) return true;
    std::cerr << "[GPIO] ERROR " << phase << " " << name << " (return=" << WEXITSTATUS(status) << ")\n";
    return false;
}

static bool release_gpio_pin(int gpio, const char* name, const char* phase) {
    std::string cmd_gpio = std::string("gpio -g mode ") + std::to_string(gpio) + " in";
    if (run_shell_command(cmd_gpio, name, phase)) return true;
    std::string cmd_raspi = std::string("raspi-gpio set ") + std::to_string(gpio) + " ip";
    if (run_shell_command(cmd_raspi, name, phase)) return true;
    return false;
}

static bool set_lock_state(int gpio, const char* name, bool active, bool active_high, const char* phase) {
    const char* logic = (active ? (active_high ? "dh" : "dl") : (active_high ? "dl" : "dh"));
    const char* value = (std::string(logic) == "dh") ? "1" : "0";
    std::string cmd_gpio = std::string("gpio -g mode ") + std::to_string(gpio) + " out && gpio -g write " + std::to_string(gpio) + " " + value;
    if (run_shell_command(cmd_gpio, name, phase)) return true;
    std::string cmd_raspi = std::string("raspi-gpio set ") + std::to_string(gpio) + " op " + logic;
    if (run_shell_command(cmd_raspi, name, phase)) return true;
    std::string cmd_pinctrl = std::string("pinctrl set ") + std::to_string(gpio) + " op pn " + logic;
    return run_shell_command(cmd_pinctrl, name, phase);
}

static void reset_lock(int gpio, const char* name, bool active_high) {
    if (!set_lock_state(gpio, name, false, active_high, "RESET")) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        set_lock_state(gpio, name, false, active_high, "RESET-RETRY");
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(RELAY_SOFT_RELEASE_MS));
    release_gpio_pin(gpio, name, "RELEASE");
}

void reset_all_locks() {
    std::cout << "[GPIO] RESET ALL LOCKS\n";
    reset_lock(MAIN_DOOR_GPIO, "MAIN DOOR", MAIN_DOOR_ACTIVE_HIGH);
    reset_lock(DELIVERY_BOX_GPIO, "DELIVERY BOX", DELIVERY_BOX_ACTIVE_HIGH);
}

static void trigger_lock(int gpio, const char* name, bool active_high, int duration_sec) {
    std::thread([gpio, name, active_high, duration_sec]() {
        {
            std::lock_guard<std::mutex> lock(relay_mutex);
            std::cout << "[GPIO] Activating " << name << " (GPIO " << gpio << ")...\n";
            EventLogger::write_event_json("door_unlock", std::string(name) + ",gpio=" + std::to_string(gpio));
            if (!set_lock_state(gpio, name, true, active_high, "ACTIVATE")) {
                std::cerr << "[GPIO] WARNING " << name << " may not have activated correctly.\n";
            }
        }
        auto start_time = std::chrono::steady_clock::now();
        
        // Chờ cửa mở ra (có timeout)
        while (true) {
            if ((gpio == MAIN_DOOR_GPIO && cancel_main_door_wait) || 
                (gpio == DELIVERY_BOX_GPIO && cancel_delivery_box_wait)) break;
            if ((gpio == MAIN_DOOR_GPIO && main_door_open) || 
                (gpio == DELIVERY_BOX_GPIO && delivery_box_open)) break;
                
            auto now = std::chrono::steady_clock::now();
            auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - start_time).count();
            if (elapsed >= duration_sec) {
                break; // Hết thời gian chờ, tự động khóa lại
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
        
        // Nếu cửa đã mở, chờ cửa đóng lại
        if ((gpio == MAIN_DOOR_GPIO && main_door_open) || 
            (gpio == DELIVERY_BOX_GPIO && delivery_box_open)) {
            while (true) {
                if ((gpio == MAIN_DOOR_GPIO && cancel_main_door_wait) || 
                    (gpio == DELIVERY_BOX_GPIO && cancel_delivery_box_wait)) break;
                if ((gpio == MAIN_DOOR_GPIO && !main_door_open) || 
                    (gpio == DELIVERY_BOX_GPIO && !delivery_box_open)) break;
                std::this_thread::sleep_for(std::chrono::milliseconds(20));
            }
        }
        
        if ((gpio == MAIN_DOOR_GPIO && cancel_main_door_wait) || 
            (gpio == DELIVERY_BOX_GPIO && cancel_delivery_box_wait)) {
            if (gpio == MAIN_DOOR_GPIO) cancel_main_door_wait = false;
            if (gpio == DELIVERY_BOX_GPIO) cancel_delivery_box_wait = false;
        }
        {
            std::lock_guard<std::mutex> lock(relay_mutex);
            // Ép Relay tắt ngay lập tức bằng cách kéo logic xuống LOW/HIGH, triệt tiêu độ trễ do float pin
            set_lock_state(gpio, name, false, active_high, "DEACTIVATE");
            
            std::this_thread::sleep_for(std::chrono::milliseconds(RELAY_SETTLE_MS));
            release_gpio_pin(gpio, name, "SOFT-RELEASE");
            std::cout << "[GPIO] " << name << " deactivated.\n";
            EventLogger::write_event_json("door_lock", std::string(name));
        }
    }).detach();
}

void trigger_main_door() {
    trigger_lock(MAIN_DOOR_GPIO, "MAIN DOOR", MAIN_DOOR_ACTIVE_HIGH, LOCK_PULSE_SECONDS);
}

void trigger_delivery_box() {
    trigger_lock(DELIVERY_BOX_GPIO, "DELIVERY BOX", DELIVERY_BOX_ACTIVE_HIGH, LOCK_PULSE_SECONDS);
}

} // namespace LockController
