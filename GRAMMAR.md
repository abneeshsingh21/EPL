# EPL Formal Grammar Specification v5.0

This document defines the complete formal grammar for the EPL (English Programming Language) v5.0.
The notation uses Extended Backus–Naur Form (EBNF) with the following conventions:

- `"keyword"` — literal keyword (case-insensitive)
- `TOKEN` — lexer token
- `rule` — parser rule reference
- `( ... )` — grouping
- `[ ... ]` — optional (zero or one)
- `{ ... }` — repetition (zero or more)
- `|` — alternation
- `(*  *)` — comment

---

## 1. Lexical Grammar

### 1.1 Whitespace and Comments

```ebnf
NEWLINE      = "\n" | "\r\n" ;
COMMENT      = "Note:" , { any_char - NEWLINE } , NEWLINE ;
(* Comments starting with "Note:" are discarded by the lexer *)
```

### 1.2 Literals

```ebnf
NUMBER       = integer | float | hex_int | octal_int | binary_int ;
integer      = digit , { digit | "_" } ;
float        = digit , { digit | "_" } , "." , digit , { digit | "_" } ;
hex_int      = "0x" , hex_digit , { hex_digit | "_" } ;
octal_int    = "0o" , octal_digit , { octal_digit | "_" } ;
binary_int   = "0b" , ("0" | "1") , { "0" | "1" | "_" } ;
digit        = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;
hex_digit    = digit | "a" | "b" | "c" | "d" | "e" | "f"
                     | "A" | "B" | "C" | "D" | "E" | "F" ;
octal_digit  = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" ;

STRING       = simple_string | triple_string ;
simple_string = '"' , { string_char | escape_seq } , '"' ;
triple_string = '"""' , { any_char } , '"""' ;
escape_seq   = "\" , ( "n" | "t" | "r" | "\" | '"' ) ;

BOOLEAN_TRUE  = "true" | "yes" ;
BOOLEAN_FALSE = "false" | "no" ;
NOTHING       = "nothing" ;

IDENTIFIER   = ( letter | "_" ) , { letter | digit | "_" } ;
letter       = "a"-"z" | "A"-"Z" ;
```

### 1.3 Keywords

```
(* Variable operations *)
Create  Set  To  Equal  Named  Variable  Of  Type  As  Remember

(* Type names *)
Integer  Decimal  Text  Boolean  List

(* I/O *)
Print  Display  Show  Say  Input  Ask

(* Control flow *)
If  Then  Otherwise  End  Break  Continue

(* Loops *)
Repeat  Times  While  For  Each  In  From  By  Step

(* Functions *)
Define  Function  Call  With  Return  Returns  Takes  That  A  An  The  Rest

(* Classes & OOP *)
Class  New  This  Extends  Implements  Interface  Abstract  Override  Super
Static  Public  Private  Protected

(* File I/O *)
Write  Read  Append  File

(* Error handling *)
Try  Catch  Finally  Throw  Assert

(* Pattern matching *)
Match  When  Default

(* Collections & modules *)
Map  Import  Use  Python  Constant  Module  Export  Yields

(* Async *)
Async  Await

(* Misc *)
Wait  Seconds  Exit  NoteBlock

(* Arithmetic helpers *)
Increase  Decrease  Add  Sort  Reverse  Multiply  Divide  Mod

(* English comparisons *)
Equals  Between  Greater  Less  Than  Plus  Minus
Is  And  Or  Not  Does  At  Least  Most  Raised

(* Web framework *)
Route  WebApp  Start  Page  Heading  SubHeading  Link  Image  Button
Form  Send  Json  Port  Shows  Responds  On  Called  Action
Placeholder  Store  Fetch  Delete  Redirect  Script  Text

(* GUI framework *)
Window  Canvas  Dialog  Layout  Row  Column  Menu  Bind
Label  TextBox  Checkbox  Dropdown  Slider  Progress  TextArea
Tab  Tree  Widget

(* Generics *)
Generic  Where

(* Enum *)
Enum
```

### 1.4 Operators

```ebnf
(* Arithmetic *)
OP_PLUS       = "+" ;
OP_MINUS      = "-" ;
OP_MULTIPLY   = "*" ;
OP_DIVIDE     = "/" ;
OP_FLOOR_DIV  = "//" ;
OP_MODULO     = "%" ;
OP_POWER      = "**" ;

(* Comparison *)
OP_GREATER    = ">" ;
OP_LESS       = "<" ;
OP_GREATER_EQ = ">=" ;
OP_LESS_EQ    = "<=" ;
OP_EQUAL      = "==" ;
OP_NOT_EQUAL  = "!=" ;

(* Assignment *)
OP_ASSIGN     = "=" ;
OP_PLUS_ASSIGN  = "+=" ;
OP_MINUS_ASSIGN = "-=" ;
OP_MUL_ASSIGN   = "*=" ;
OP_DIV_ASSIGN   = "/=" ;
OP_MOD_ASSIGN   = "%=" ;

(* Delimiters *)
LPAREN       = "(" ;
RPAREN       = ")" ;
LBRACKET     = "[" ;
RBRACKET     = "]" ;
LBRACE       = "{" ;
RBRACE       = "}" ;
DOT          = "." ;
COMMA        = "," ;
COLON        = ":" ;
DOUBLE_COLON = "::" ;
ARROW        = "->" ;
PIPE         = "|" ;
QUESTION     = "?" ;
```

### 1.5 Multi-Word Comparison Tokens

The lexer recognizes these multi-word sequences as single tokens:

```
"is greater than or equal to"  →  OP_GREATER_EQ
"is less than or equal to"     →  OP_LESS_EQ
"is greater than"              →  OP_GREATER
"is less than"                 →  OP_LESS
"is equal to"                  →  OP_EQUAL
"is not equal to"              →  OP_NOT_EQUAL
"is at least"                  →  OP_GREATER_EQ
"is at most"                   →  OP_LESS_EQ
"does not equal"               →  OP_NOT_EQUAL
"raised to"                    →  OP_POWER
```

---

## 2. Syntactic Grammar

### 2.1 Program Structure

```ebnf
program       = { statement } , EOF ;
statement     = ( declaration_stmt
              | assignment_stmt
              | io_stmt
              | control_stmt
              | function_stmt
              | class_stmt
              | error_stmt
              | collection_stmt
              | file_stmt
              | module_stmt
              | async_stmt
              | web_stmt
              | gui_stmt
              | misc_stmt ) , [ "." ] ;
```

### 2.2 Declarations

```ebnf
declaration_stmt = var_declaration | const_declaration | enum_def ;

var_declaration  = "Create" , [ article ] , [ type_name ] , [ "Variable" ] ,
                   [ "Named" ] , IDENTIFIER ,
                   ( "equal" , [ "to" ] | "=" | "as" ) , expression
                 | "Remember" , [ article ] , [ type_name ] , IDENTIFIER ,
                   "=" , expression ;

const_declaration = "Constant" , IDENTIFIER , "=" , expression ;

enum_def        = "Enum" , IDENTIFIER , [ "as" ] ,
                  IDENTIFIER , { "," , IDENTIFIER } , [ "End" ] ;

article         = "a" | "an" | "the" ;

type_name       = "integer" | "decimal" | "text" | "boolean" | "list" ;
```

### 2.3 Assignments

```ebnf
assignment_stmt  = set_assignment | shorthand_assignment ;

set_assignment   = "Set" , IDENTIFIER , "to" , expression ;

shorthand_assignment = target , ( "=" | "+=" | "-=" | "*=" | "/=" | "%=" ) , expression ;

target           = IDENTIFIER
                 | IDENTIFIER , "[" , expression , "]"
                 | IDENTIFIER , "." , IDENTIFIER ;

increase_stmt    = "Increase" , IDENTIFIER , "by" , expression ;
decrease_stmt    = "Decrease" , IDENTIFIER , "by" , expression ;
multiply_stmt    = "Multiply" , IDENTIFIER , "by" , expression ;
divide_stmt      = "Divide"   , IDENTIFIER , "by" , expression ;
```

### 2.4 I/O Statements

```ebnf
io_stmt          = print_stmt | input_stmt | ask_stmt ;

print_stmt       = ( "Print" | "Display" | "Show" | "Say" ) , expression ;

input_stmt       = "Input" , IDENTIFIER , [ "with" , [ "prompt" ] , STRING ] ;

ask_stmt         = "Ask" , [ STRING ] , [ "and" ] , [ "store" ] , [ "in" ] , IDENTIFIER ;
```

### 2.5 Control Flow

```ebnf
control_stmt     = if_stmt | while_stmt | repeat_stmt | for_stmt
                 | break_stmt | continue_stmt | match_stmt ;

if_stmt          = "If" , expression , [ "then" ] ,
                   { statement } ,
                   { "Otherwise" , ( if_stmt | { statement } ) } ,
                   "End" ;

while_stmt       = "While" , expression ,
                   { statement } ,
                   "End" ;

repeat_stmt      = "Repeat" , expression , "times" ,
                   { statement } ,
                   "End" ;

for_stmt         = for_each | for_range ;

for_each         = "For" , "each" , IDENTIFIER , "in" , expression ,
                   { statement } ,
                   "End" ;

for_range        = "For" , IDENTIFIER , "from" , expression ,
                   "to" , expression , [ "step" , expression ] ,
                   { statement } ,
                   "End" ;

break_stmt       = "Break" ;
continue_stmt    = "Continue" ;

match_stmt       = "Match" , expression ,
                   { "When" , expression , { "or" , expression } ,
                     { statement } } ,
                   [ "Default" , { statement } ] ,
                   "End" ;
```

### 2.6 Functions

```ebnf
function_stmt    = function_def | function_def_short | call_stmt | return_stmt ;

function_def     = "Define" , [ article ] , "Function" , [ "Named" ] , IDENTIFIER ,
                   [ ( "that" , "takes" | "takes" ) , param_list ] ,
                   [ "and" , "returns" , [ type_name ] ] ,
                   { statement } ,
                   "End" ;

function_def_short = "Function" , IDENTIFIER ,
                     [ "takes" , param_list ] ,
                     [ "and" , "returns" , type_name ] ,
                     { statement } ,
                     "End" ;

param_list       = "nothing"
                 | parameter , { ( "and" | "," ) , parameter } ;

parameter        = [ type_name ] , IDENTIFIER , [ "=" , expression ]
                 | "rest" , IDENTIFIER ;

call_stmt        = "Call" , IDENTIFIER , [ "with" , arg_list ] ;

arg_list         = expression , { ( "and" | "," ) , expression } ;

return_stmt      = "Return" , [ expression ] ;
```

### 2.7 Classes and OOP

```ebnf
class_stmt       = class_def | interface_def | visibility_modifier
                 | static_method | abstract_method | override_method
                 | super_call ;

class_def        = "Class" , IDENTIFIER ,
                   [ "extends" , IDENTIFIER ] ,
                   [ "implements" , IDENTIFIER , { "," , IDENTIFIER } ] ,
                   { class_member } ,
                   "End" ;

class_member     = var_declaration
                 | function_def | function_def_short
                 | static_method
                 | abstract_method
                 | override_method
                 | visibility_modifier ;

interface_def    = "Interface" , IDENTIFIER ,
                   [ "extends" , IDENTIFIER , { "," , IDENTIFIER } ] ,
                   { method_signature } ,
                   "End" ;

method_signature = "Function" , IDENTIFIER , "takes" , param_list ,
                   [ "and" , "returns" , type_name ] ;

visibility_modifier = ( "Public" | "Private" | "Protected" ) , class_member ;

static_method    = "Static" , ( function_def | function_def_short ) ;

abstract_method  = "Abstract" , "Function" , IDENTIFIER ,
                   "takes" , param_list , "and" , "returns" , type_name ;

override_method  = "Override" , ( function_def | function_def_short ) ;

super_call       = "Super" , [ "." , IDENTIFIER ] , [ "(" , [ arg_list ] , ")" ] ;

new_expr         = "New" , IDENTIFIER , [ "(" , [ arg_list ] , ")" ] ;
```

### 2.8 Error Handling

```ebnf
error_stmt       = try_catch | throw_stmt | assert_stmt ;

try_catch        = "Try" ,
                   { statement } ,
                   [ "Catch" , [ IDENTIFIER ] ,
                     { statement } ] ,
                   [ "Finally" ,
                     { statement } ] ,
                   "End" ;

throw_stmt       = "Throw" , expression ;

assert_stmt      = "Assert" , expression ;
```

### 2.9 Collections

```ebnf
collection_stmt  = add_to | sort_stmt | reverse_stmt ;

add_to           = "Add" , expression , "to" , IDENTIFIER ;

sort_stmt        = "Sort" , IDENTIFIER ;

reverse_stmt     = "Reverse" , IDENTIFIER ;

list_literal     = "[" , [ expression , { "," , expression } ] , "]" ;

map_literal      = "Map" , "with" , IDENTIFIER , "=" , expression ,
                   { "and" , IDENTIFIER , "=" , expression } ;
```

### 2.10 File I/O

```ebnf
file_stmt        = write_stmt | append_stmt ;

write_stmt       = "Write" , expression , "to" , "file" , expression ;

append_stmt      = "Append" , expression , "to" , "file" , expression ;

read_expr        = "Read" , "file" , expression ;
```

### 2.11 Modules and Imports

```ebnf
module_stmt      = import_stmt | use_stmt | module_def | export_stmt ;

import_stmt      = "Import" , STRING , [ "as" , IDENTIFIER ] ;

use_stmt         = "Use" , "python" , STRING , [ "as" , IDENTIFIER ] ;

module_def       = "Module" , IDENTIFIER ,
                   { "Export" , IDENTIFIER } ,
                   { statement } ,
                   "End" ;

export_stmt      = "Export" , IDENTIFIER ;
```

### 2.12 Async/Await

```ebnf
async_stmt       = async_function | await_stmt ;

async_function   = "Async" , "Function" , IDENTIFIER ,
                   [ "takes" , param_list ] ,
                   [ "and" , "returns" , type_name ] ,
                   { statement } ,
                   "End" ;

await_stmt       = "Await" , expression ;
```

### 2.13 Generators

```ebnf
yield_stmt       = "Yields" , [ expression ] ;
```

---

## 3. Expression Grammar

Operator precedence from lowest (1) to highest (7):

```ebnf
expression       = ternary ;

ternary          = or_expr , [ "if" , or_expr , "otherwise" , or_expr ] ;

or_expr          = and_expr , { "or" , and_expr } ;                       (* level 1 *)

and_expr         = comparison , { "and" , comparison } ;                  (* level 2 *)

comparison       = addition , [ comp_op , addition ]                      (* level 3 *)
                 | addition , "is" , "between" , addition , "and" , addition ;

comp_op          = ">" | "<" | ">=" | "<=" | "==" | "!="
                 | "is greater than" | "is less than"
                 | "is equal to" | "is not equal to"
                 | "is greater than or equal to"
                 | "is less than or equal to"
                 | "equals" | "not equals" | "does not equal"
                 | "at least" | "at most" ;

addition         = multiplication , { ( "+" | "-" ) , multiplication } ;  (* level 4 *)

multiplication   = power , { ( "*" | "/" | "//" | "%" | "mod" ) , power } ;(* level 5 *)

power            = unary , [ ( "**" | "raised to" ) , power ] ;           (* level 6, right-assoc *)

unary            = ( "not" | "-" ) , unary                                (* level 7 *)
                 | postfix ;

postfix          = primary , { "." , IDENTIFIER , [ "(" , [ arg_list ] , ")" ]
                             | "[" , subscript , "]"
                             | "::" , IDENTIFIER , [ "(" , [ arg_list ] , ")" ] } ;

subscript        = expression                                             (* index *)
                 | [ expression ] , ":" , [ expression ] , [ ":" , [ expression ] ] ; (* slice *)

primary          = NUMBER
                 | STRING
                 | BOOLEAN_TRUE | BOOLEAN_FALSE
                 | NOTHING
                 | IDENTIFIER , [ "(" , [ arg_list ] , ")" ]
                 | "(" , expression , ")"
                 | list_literal
                 | map_literal
                 | lambda_expr
                 | given_expr
                 | new_expr
                 | read_expr
                 | "this"
                 | "await" , expression
                 | "super" , [ "." , IDENTIFIER ] , [ "(" , [ arg_list ] , ")" ]
                 | "Call" , IDENTIFIER , [ "with" , arg_list ] ;

lambda_expr      = "lambda" , IDENTIFIER , { "," , IDENTIFIER } , "->" , expression ;

given_expr       = "given" , IDENTIFIER , { "," , IDENTIFIER } ,
                   ( "return" | "->" ) , expression ;
```

---

## 4. Web Framework Grammar

```ebnf
web_stmt         = webapp_def | route_def | start_server | page_def
                 | send_stmt | store_stmt | fetch_stmt | delete_stmt
                 | redirect_stmt | script_block ;

webapp_def       = "Create" , "WebApp" , [ "called" ] , IDENTIFIER ;

route_def        = "Route" , STRING , [ "shows" | "responds" , [ "with" ] ] ,
                   { html_element | statement } ,
                   "End" ;

start_server     = "Start" , IDENTIFIER , [ "on" , [ "port" ] ] , expression ;

page_def         = "Page" , STRING ,
                   { html_element } ,
                   "End" ;

html_element     = "Heading" , STRING
                 | "SubHeading" , STRING
                 | "Text" , STRING
                 | "Link" , STRING , [ "to" , STRING ]
                 | "Image" , STRING
                 | "Button" , STRING , [ "does" , expression ]
                 | "Form" , [ "action" , STRING ] , { html_element } , "End"
                 | "Input" , STRING , [ "placeholder" , STRING ]
                 | "List" , expression ;

send_stmt        = "Send" , [ "json" | "text" ] , expression ;

store_stmt       = "Store" , [ "form" , STRING ] , [ expression ] , "in" , STRING ;

fetch_stmt       = "Fetch" , STRING ;

delete_stmt      = "Delete" , "from" , STRING , [ "at" , expression ] ;

redirect_stmt    = "Redirect" , [ "to" ] , STRING ;

script_block     = "Script" , { statement } , "End" ;
```

---

## 5. GUI Framework Grammar

```ebnf
gui_stmt         = window_def | layout_block | bind_event
                 | dialog_stmt | menu_def | canvas_draw ;

window_def       = "Window" , expression , [ NUMBER , ( "by" | "x" ) , NUMBER ] ,
                   { widget } ,
                   "End" ;

widget           = "Label" , STRING , [ "called" , IDENTIFIER ]
                 | "TextBox" , [ "called" , IDENTIFIER ] , [ "placeholder" , STRING ]
                 | "Button" , STRING , [ "called" , IDENTIFIER ] , [ "does" , expression ]
                 | "Checkbox" , [ "called" , IDENTIFIER ]
                 | "Dropdown" , list_literal , [ "called" , IDENTIFIER ]
                 | "Slider" , NUMBER , "to" , NUMBER , [ "called" , IDENTIFIER ]
                 | "Progress" , expression , [ "called" , IDENTIFIER ]
                 | "TextArea" , [ "called" , IDENTIFIER ] , [ "placeholder" , STRING ] ;

layout_block     = ( "Row" | "Column" ) , { widget } , "End" ;

bind_event       = "Bind" , IDENTIFIER , STRING , "to" , IDENTIFIER ;

dialog_stmt      = "Dialog" , STRING , [ "type" , STRING ] ;

menu_def         = "Menu" , STRING , { menu_item } , "End" ;

canvas_draw      = "Canvas" , IDENTIFIER , "draw" , shape , { property } ;

shape            = "rect" | "circle" | "line" | "text" ;
```

---

## 6. Miscellaneous

```ebnf
misc_stmt        = wait_stmt | exit_stmt | noteblock ;

wait_stmt        = "Wait" , expression , [ "seconds" ] ;

exit_stmt        = "Exit" ;

noteblock        = "NoteBlock" , { any } , "End" ;
```

---

## 7. Statement Termination

Statements in EPL are terminated by:
1. A period `.` (optional, English-style)
2. A newline
3. The start of a new statement keyword

Example:
```
Create age equal to 20.
Print age
```

---

## 8. Operator Precedence Table

| Level | Operators | Associativity | Description |
|-------|-----------|---------------|-------------|
| 1 (lowest) | `or` | Left | Logical OR |
| 2 | `and` | Left | Logical AND |
| 3 | `>` `<` `>=` `<=` `==` `!=` `is between` `equals` `at least` `at most` | Left | Comparison |
| 4 | `+` `-` | Left | Addition / Subtraction |
| 5 | `*` `/` `//` `%` `mod` | Left | Multiplication / Division / Modulo |
| 6 | `**` `raised to` | Right | Exponentiation |
| 7 (highest) | `not` `-` (unary) | Right | Unary operators |

---

## 9. Conformance Notes

- Keywords are **case-insensitive** in the lexer (e.g., `CREATE`, `Create`, `create` all produce the same token).
- Identifiers are **case-sensitive** (e.g., `myVar` ≠ `MyVar`).
- The period `.` serves dual purpose: property access operator and optional statement terminator. The parser disambiguates based on context.
- English comparison phrases (e.g., "is greater than") are resolved by the lexer into standard comparison tokens.
- The `and` keyword is context-sensitive: it acts as a logical operator in expressions and as a separator in parameter/argument lists.
