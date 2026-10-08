// This file is part of www.nand2tetris.org
// and the book "The Elements of Computing Systems"
// by Nisan and Schocken, MIT Press.
// File name: projects/04/Fill.asm

// Runs an infinite loop that listens to the keyboard input.
// When a key is pressed (any key), the program blackens the screen,
// i.e. writes "black" in every pixel;
// the screen should remain fully black as long as the key is pressed. 
// When no key is pressed, the program clears the screen, i.e. writes
// "white" in every pixel;
// the screen should remain fully clear as long as no key is pressed.

// Put your code here.
// int main() {
//    int R0 = 3;
//    int R1 = 5;
// =>    int R2 = 0;
@2
M=0
//    while (R0 > 0) {
// => loop:
(loop)
// =>    if (R0 <= 0) goto exit1;
@0
D=M
@exit1
D;JLE

// =>  R2 = R2 + R1;
@1
D=M
@2
M=D+M

// =>  R0 = R0 - 1;
@0
M=M-1

//    printf("R0=%d R1=%d R2=%d\n", R0, R1, R2);
// =>  goto loop;
@loop
0;JMP

// => exit1:
(exit1)
@exit1
0;JMP
// }