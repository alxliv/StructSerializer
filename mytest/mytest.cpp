// mytest.cpp : This file contains the 'main' function. Program execution begins and ends there.
//

#include <iostream>
#include <cassert>
#include <cmath>
#include "mytypes.h"
#include "..\py_helpers/out/myTestStruct_serial.h"


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

#if 1
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

    assert(myTestStruct_equals(&s, &s2));
    printf("all done OK\n");
#endif

    return 0;   
}
