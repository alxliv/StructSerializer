// mytest.cpp : This file contains the 'main' function. Program execution begins and ends there.
//

#include <iostream>
#include <cassert>
#include <cmath>
#include "mytypes.h"
#include "..\py_helpers/out/autogen_to_from_json.h"


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

    AnotherTestStruct another;
    another.bounding = { 1.34, 5.67 };
    another.center = { 6.78f, 9.0f };
    another.color = COLOR_BLUE;
    another.points[0] = { 1,2 };
    another.points[1] = { 3,4 };
    another.points[2] = { 5,6 };
    another.points[3] = { 7,8 };

    another.some_tt.flags = 0x34;
    another.some_tt.status = 0xabcd;
    another.some_tt.tt_size = { 0.3,0.6 };


#if 1
    cJSON* root = cJSON_CreateObject();

    // Serialize myTestStruct under its own key
    {
        cJSON* s_obj = cJSON_CreateObject();
        myTestStruct_to_json(&s, s_obj);
        cJSON_AddItemToObject(root, "myTestStruct", s_obj);
    }

    // Serialize AnotherTestStruct under its own key
    {
        cJSON* a_obj = cJSON_CreateObject();
        AnotherTestStruct_to_json(&another, a_obj);
        cJSON_AddItemToObject(root, "AnotherTestStruct", a_obj);
    }

    char* json_str = cJSON_Print(root);
    printf("%s\n", json_str);

    cJSON* parsed = cJSON_Parse(json_str);

    myTestStruct s2 = { 0 };
    {
        const cJSON* s_obj = cJSON_GetObjectItem(parsed, "myTestStruct");
        assert(s_obj && cJSON_IsObject(s_obj));
        myTestStruct_from_json(&s2, s_obj);
    }

    AnotherTestStruct a2 = { 0 };
    {
        const cJSON* a_obj = cJSON_GetObjectItem(parsed, "AnotherTestStruct");
        assert(a_obj && cJSON_IsObject(a_obj));
        AnotherTestStruct_from_json(&a2, a_obj);
    }

    cJSON_Delete(root);
    cJSON_Delete(parsed);
    free(json_str);

    assert(myTestStruct_equals(&s, &s2));
    assert(AnotherTestStruct_equals(&another, &a2));
#endif

    printf("all done OK\n");
    return 0;   
}
