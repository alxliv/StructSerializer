// mytest.cpp : This file contains the 'main' function. Program execution begins and ends there.
//

#include <iostream>
#include <cassert>
#include <cmath>
#include "../py_helpers/myTestStruct_serial.h"
#include "../cJSON/cJSON.h"

static inline bool feqf(float a, float b, float eps =1e-6f) {
    return std::fabs(a - b) <= eps;
}
static inline bool feqd(double a, double b, double eps =1e-9) {
    return std::fabs(a - b) <= eps;
}

bool IsEqual(const myTestStruct& a, const myTestStruct& b) {
    if (!feqf(a.center.x, b.center.x) || !feqf(a.center.y, b.center.y)) return false;
    if (!feqd(a.bounding.width, b.bounding.width) || !feqd(a.bounding.height, b.bounding.height)) return false;
    if (a.color != b.color) return false;
    for (int i =0; i <5; ++i) {
        if (!feqf(a.values[i], b.values[i])) return false;
    }
    return true;
}

int main()
{
    myTestStruct s;
    s.center.x = 1.0f;
    s.center.y = 2.0f;
    s.bounding.width = 3.0;
    s.bounding.height = 4.0;
    s.color = COLOR_GREEN;
    s.values[0] = 0.1f;
    s.values[1] = 0.2f;
    s.values[2] = 0.3f;
    s.values[3] = 0.4f;
    s.values[4] = 0.5f;

    cJSON* root = cJSON_CreateObject();
    myTestStruct_to_json(&s, root);
    char* json_str = cJSON_Print(root);
    printf("%s\n", json_str);

    myTestStruct s2 = { 0 };
    cJSON* parsed = cJSON_Parse(json_str);
    myTestStruct_from_json(&s2, parsed);
    cJSON_Delete(root);
    cJSON_Delete(parsed);
    free(json_str);

    assert(IsEqual(s, s2));
    printf("all done OK\n");
    return 0;   
}
