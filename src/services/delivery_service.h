#pragma once
#include <string>

// Xác thực và tiêu thụ mã giao hàng một lần
namespace DeliveryService {
    bool verify_and_consume_code(const std::string& code, std::string& creator_name);
}
