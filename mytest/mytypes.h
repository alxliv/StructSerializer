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
    Point origin;
    Size size;
} Rect;

typedef struct {
    Point center;
    Size bounding;
    Color color;
    float values[5];
} myTestStruct;

typedef struct {
    unsigned int status;
    char flags;
    Size tt_size;
} SomeTT;

#define NUM_POINTS (4)
typedef struct {
    Point center;
    Size bounding;
    Color color;
    SomeTT some_tt;
    Point points[NUM_POINTS];
} AnotherTestStruct;
