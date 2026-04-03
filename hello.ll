; ModuleID = "epl_program"
target triple = "x86_64-pc-windows-msvc"
target datalayout = ""

declare i32 @"printf"(i8* %".1", ...)

declare i32 @"puts"(i8* %".1")

declare i32 @"sprintf"(i8* %".1", i8* %".2", ...)

declare i8* @"malloc"(i64 %".1")

declare void @"free"(i8* %".1")

declare i64 @"strlen"(i8* %".1")

declare i8* @"strcpy"(i8* %".1", i8* %".2")

declare i8* @"strcat"(i8* %".1", i8* %".2")

declare i32 @"strcmp"(i8* %".1", i8* %".2")

declare void @"exit"(i32 %".1")

declare void @"_sleep"(i32 %".1")

declare i8* @"fopen"(i8* %".1", i8* %".2")

declare i32 @"fclose"(i8* %".1")

declare i32 @"fprintf"(i8* %".1", i8* %".2", ...)

declare i8* @"epl_list_new"()

declare void @"epl_list_push_raw"(i8* %".1", i32 %".2", i64 %".3")

declare i64 @"epl_list_get_int"(i8* %".1", i64 %".2")

declare i32 @"epl_list_get_tag"(i8* %".1", i64 %".2")

declare void @"epl_list_set_int"(i8* %".1", i64 %".2", i64 %".3")

declare i32 @"epl_list_length"(i8* %".1")

declare void @"epl_list_remove_raw"(i8* %".1", i64 %".2")

declare i32 @"epl_list_contains_int"(i8* %".1", i64 %".2")

declare i8* @"epl_list_slice"(i8* %".1", i64 %".2", i64 %".3", i64 %".4")

declare void @"epl_list_print"(i8* %".1")

declare i8* @"epl_map_new"()

declare void @"epl_map_set_int"(i8* %".1", i8* %".2", i64 %".3")

declare void @"epl_map_set_str"(i8* %".1", i8* %".2", i8* %".3")

declare i64 @"epl_map_get_int"(i8* %".1", i8* %".2")

declare i8* @"epl_map_get_str"(i8* %".1", i8* %".2")

declare i8* @"epl_object_new"(i8* %".1")

declare void @"epl_object_set_int"(i8* %".1", i8* %".2", i64 %".3")

declare void @"epl_object_set_str"(i8* %".1", i8* %".2", i8* %".3")

declare i64 @"epl_object_get_int"(i8* %".1", i8* %".2")

declare i8* @"epl_object_get_str"(i8* %".1", i8* %".2")

declare i8* @"epl_string_index"(i8* %".1", i64 %".2")

declare i64 @"epl_string_length"(i8* %".1")

declare i8* @"epl_string_upper"(i8* %".1")

declare i8* @"epl_string_lower"(i8* %".1")

declare i32 @"epl_string_contains"(i8* %".1", i8* %".2")

declare i8* @"epl_string_substring"(i8* %".1", i64 %".2", i64 %".3")

declare i8* @"epl_string_replace"(i8* %".1", i8* %".2", i8* %".3")

declare i8* @"epl_string_trim"(i8* %".1")

declare i32 @"epl_string_starts_with"(i8* %".1", i8* %".2")

declare i32 @"epl_string_ends_with"(i8* %".1", i8* %".2")

declare i8* @"epl_string_split"(i8* %".1", i8* %".2")

declare i8* @"epl_string_reverse"(i8* %".1")

declare i8* @"epl_input"(i8* %".1")

declare i8* @"epl_input_no_prompt"()

declare i8* @"epl_int_to_string"(i64 %".1")

declare i8* @"epl_float_to_string"(double %".1")

declare i64 @"epl_string_to_int"(i8* %".1")

declare double @"epl_string_to_float"(i8* %".1")

declare double @"epl_power"(double %".1", double %".2")

declare double @"epl_floor"(double %".1")

declare double @"epl_sqrt"(double %".1")

declare double @"epl_ceil"(double %".1")

declare double @"epl_log"(double %".1")

declare double @"epl_sin"(double %".1")

declare double @"epl_cos"(double %".1")

declare double @"epl_fabs"(double %".1")

declare i8* @"epl_file_read"(i8* %".1")

declare i32 @"epl_try_begin"()

declare void @"epl_try_end"()

declare void @"epl_throw"(i8* %".1")

declare i8* @"epl_get_exception"()

declare void @"epl_string_free"(i8* %".1")

declare void @"epl_list_free"(i8* %".1")

declare void @"epl_map_free"(i8* %".1")

declare void @"epl_object_free"(i8* %".1")

declare i8* @"epl_arena_alloc"(i64 %".1")

declare void @"epl_arena_reset"()

@"fmt_int" = private constant [5 x i8] c"%lld\00"
@"fmt_float" = private constant [3 x i8] c"%g\00"
@"fmt_str" = private constant [3 x i8] c"%s\00"
@"fmt_true" = private constant [5 x i8] c"true\00"
@"fmt_false" = private constant [6 x i8] c"false\00"
@"fmt_nothing" = private constant [8 x i8] c"nothing\00"
@"fmt_newline" = private constant [2 x i8] c"\0a\00"
@"fmt_int_nl" = private constant [6 x i8] c"%lld\0a\00"
@"fmt_float_nl" = private constant [4 x i8] c"%g\0a\00"
@"fmt_str_nl" = private constant [4 x i8] c"%s\0a\00"
define i32 @"main"()
{
entry:
  %".2" = bitcast [14 x i8]* @"str_10" to i8*
  %".3" = bitcast [4 x i8]* @"fmt_str_nl" to i8*
  %".4" = call i32 (i8*, ...) @"printf"(i8* %".3", i8* %".2")
  %".5" = bitcast [47 x i8]* @"str_11" to i8*
  %".6" = bitcast [4 x i8]* @"fmt_str_nl" to i8*
  %".7" = call i32 (i8*, ...) @"printf"(i8* %".6", i8* %".5")
  ret i32 0
}

@"str_10" = private constant [14 x i8] c"Hello, World!\00"
@"str_11" = private constant [47 x i8] c"Welcome to EPL - English Programming Language!\00"