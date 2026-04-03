package com.epl.app

fun sayHello(): Any {
    println("Hello from a function!")
    return Unit
}
fun greet(name: Any): Any {
    println((("Hello, " + name) + "! Welcome to EPL"))
    return Unit
}
fun add(a: Any, b: Any): Any {
    return (a + b)
}
fun factorial(n: Any): Any {
    if ((n <= 1)) {
        return 1
    }
    return (n * factorial((n - 1)))
}
fun countTo(limit: Any): Any {
    var current = 1
    while ((current <= limit)) {
        println(current)
        current = (current + 1)
    }
    return Unit
}
fun main() {
    sayHello()
    greet("Abneesh")
    greet("World")
    var result = add(5, 10)
    println(("5 + 10 = " + result))
    var fact5 = factorial(5)
    println(("Factorial of 5 = " + fact5))
    println("Counting to 3:")
    countTo(3)
}