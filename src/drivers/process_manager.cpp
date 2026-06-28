#include "process_manager.h"
#include "config/config.h"
#include "drivers/lock_controller.h"
#include "services/event_logger.h"
#include <iostream>
#include <cstdio>
#include <cstdlib>
#include <unistd.h>

namespace ProcessManager {

std::atomic<bool> card_event(false);
std::atomic<bool> face_event(false);
std::atomic<bool> face_enroll_event(false);
std::atomic<int> rfid_mode(0);

static std::mutex data_mutex;
static std::string scanned_uid;
static std::string recognized_face_name;
static std::string enroll_status;

std::string get_scanned_uid() {
    std::lock_guard<std::mutex> lock(data_mutex);
    return scanned_uid;
}

std::string get_recognized_face_name() {
    std::lock_guard<std::mutex> lock(data_mutex);
    return recognized_face_name;
}

std::string get_enroll_status() {
    std::lock_guard<std::mutex> lock(data_mutex);
    return enroll_status;
}

void start_web_services() {
    std::cout << "[SYSTEM] Starting Python Services...\n";
    system("pkill -f server.py");
    system("pkill -f event_bridge.py");
    std::string cmd_server = std::string("sudo -u lckien nohup ") + WEB_SERVER_PATH + " > ../web_server.log 2>&1 &";
    std::string cmd_bridge = std::string("sudo -u lckien nohup ") + EVENT_BRIDGE_PATH + " > ../event_bridge.log 2>&1 &";
    system(cmd_server.c_str());
    system(cmd_bridge.c_str());
}

void rfid_task() {
    std::cout << "[RFID] Don dep cac tien trinh cu...\n";
    system("sudo pkill -f rfid_driver.py");
    usleep(DRIVER_CLEANUP_DELAY_US);
    std::cout << "[RFID] Khoi dong Driver giao tiep phan cung...\n";
    FILE* pipe = popen(RFID_DRIVER_PATH, "r");
    if (!pipe) {
        std::cerr << "[RFID] LOI: Khong the khoi dong Python Driver!\n";
        return;
    }
    char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        std::string line(buffer);
        line.erase(line.find_last_not_of(" \n\r\t") + 1);
        if (line.rfind("SCAN:", 0) == 0) {
            {
                std::lock_guard<std::mutex> lock(data_mutex);
                scanned_uid = line.substr(5);
            }
            card_event = true;
        }
    }
    pclose(pipe);
}

void face_task() {
    std::cout << "[FACE] Don dep tien trinh camera cu...\n";
    system("sudo pkill -f face_engine.py");
    usleep(DRIVER_CLEANUP_DELAY_US);
    std::cout << "[FACE] Khoi dong AI Camera...\n";
    FILE* pipe = popen(FACE_ENGINE_PATH, "r");
    if (!pipe) {
        std::cerr << "[FACE] LOI: Khong the khoi dong Camera Driver!\n";
        return;
    }
    char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        std::string line(buffer);
        line.erase(line.find_last_not_of(" \n\r\t") + 1);
        if (line.rfind("FACE:", 0) == 0) {
            {
                std::lock_guard<std::mutex> lock(data_mutex);
                recognized_face_name = line.substr(5);
            }
            face_event = true;
        } else if (line.rfind("ENROLL:", 0) == 0) {
            {
                std::lock_guard<std::mutex> lock(data_mutex);
                enroll_status = line.substr(7);
            }
            face_enroll_event = true;
        }
    }
    pclose(pipe);
}

void sensor_task() {
    std::cout << "[SENSOR] Don dep tien trinh cu...\n";
    system("sudo pkill -f sensor_driver.py");
    usleep(DRIVER_CLEANUP_DELAY_US);
    std::cout << "[SENSOR] Khoi dong Driver...\n";
    FILE* pipe = popen(SENSOR_DRIVER_PATH, "r");
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
            if (is_open != LockController::main_door_open.load()) {
                LockController::main_door_open = is_open;
                EventLogger::write_event_json(is_open ? "physical_door_open" : "physical_door_close", "MAIN DOOR");
                EventLogger::update_door_status_file(LockController::main_door_open, LockController::delivery_box_open);
            }
        } else if (line.rfind("SENSOR:DELIVERY_BOX:", 0) == 0) {
            std::string state = line.substr(20);
            bool is_open = (state == "OPEN");
            if (is_open != LockController::delivery_box_open.load()) {
                LockController::delivery_box_open = is_open;
                EventLogger::write_event_json(is_open ? "physical_door_open" : "physical_door_close", "DELIVERY BOX");
                EventLogger::update_door_status_file(LockController::main_door_open, LockController::delivery_box_open);
            }
        }
    }
    pclose(pipe);
}

} // namespace ProcessManager
