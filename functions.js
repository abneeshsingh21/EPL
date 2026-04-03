function sayHello() {
  console.log("Hello from a function!");
}
sayHello();
function greet(name) {
  console.log((("Hello, " + name) + "! Welcome to EPL"));
}
greet("Abneesh");
greet("World");
function add(a, b) {
  return (a + b);
}
let result = add(5, 10);
console.log(("5 + 10 = " + result));
function factorial(n) {
  if ((n <= 1)) {
    return 1;
  }
  return (n * factorial((n - 1)));
}
let fact5 = factorial(5);
console.log(("Factorial of 5 = " + fact5));
function countTo(limit) {
  let current = 1;
  while ((current <= limit)) {
    console.log(current);
    current = (current + 1);
  }
}
console.log("Counting to 3:");
countTo(3);