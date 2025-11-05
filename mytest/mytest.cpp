// mytest.cpp : This file contains the 'main' function. Program execution begins and ends there.
//

#include <iostream>
#include "mytypes.h"


int main()
{
    std::cout << "Hello World!\n";
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
    (void)s;
    printf("all done\n");
}
