cmake_minimum_required(VERSION 3.10)
project(SmartDoorPi C CXX)

# Bật chuẩn C++14 trở lên để dùng các tính năng hiện đại
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Tối ưu: Tắt LVGL examples và demos vì không cần thiết
set(CONFIG_LV_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(CONFIG_LV_BUILD_DEMOS OFF CACHE BOOL "" FORCE)

# 1. Thêm thư viện lõi LVGL
add_subdirectory(lvgl)

# 2. Khai báo các file mã nguồn C++ của dự án
set(SOURCES
    src/main.cpp
    src/ui/ui_app.cpp
)

# 3. Tạo file thực thi tên là "smart_door_app"
add_executable(smart_door_app ${SOURCES})

# 4. Chỉ định thư mục chứa các file header (.h)
target_include_directories(smart_door_app PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/lvgl
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# 5. Liên kết file thực thi với thư viện LVGL và thư viện hệ thống (pthread, SDL2)
target_link_libraries(smart_door_app PRIVATE lvgl pthread SDL2)
