// This file is part of www.nand2tetris.org
// and the book "The Elements of Computing Systems"
// by Nisan and Schocken, MIT Press.
// File name: projects/04/Mult.asm

// Multiplies R0 and R1 and stores the result in R2.
// (R0, R1, R2 refer to RAM[0], RAM[1], and RAM[2], respectively.)

// Put your code here.
// Runs an infinite loop that listens to the keyboard input.
// When a key is pressed (any key), the program blackens the screen.
// When no key is pressed, the program clears the screen.

(FOREVER)
// arr = SCREEN
@SCREEN
D=A
@arr
M=D

// n=8192
@8192
D=A
@n
M=D
// i = 0
@i
M=0
(LOOP)
// if (i==n) goto ENDLOOP
@i
D=M
@n
D=D-M
@ENDLOOP
D;JEQ

// if (*KBD != 0)
@KBD
D=M
@ELSE
D;JEQ

// RAM[arr+i] = -1
@arr
D=M
@i
A=D+M
M=-1

@ENDIF
0;JMP
(ELSE)
// RAM[arr+i] = 0
@arr
D=M
@i
A=D+M
M=0

(ENDIF)
// i++
@i
M=M+1

@LOOP
0;JMP

(ENDLOOP)
@FOREVER
0;JMP