#pragma once

typedef enum {
    COLOR_RED,
    COLOR_GREEN,
    COLOR_BLUE
} Color;

typedef struct {
    float x;
    float y;
} Point;

typedef struct {
    double width;
    double height;
} Size;

typedef struct {
    Point center;
    Size bounding;
    Color color;
    float values[5];
} myTestStruct;

