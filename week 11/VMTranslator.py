#!/usr/bin/env python3
import os
import sys


class Parser:
    C_ARITHMETIC = "C_ARITHMETIC"
    C_PUSH = "C_PUSH"
    C_POP = "C_POP"
    C_LABEL = "C_LABEL"
    C_GOTO = "C_GOTO"
    C_IF = "C_IF"
    C_FUNCTION = "C_FUNCTION"
    C_RETURN = "C_RETURN"
    C_CALL = "C_CALL"

    ARITHMETIC_CMDS = {
        "add", "sub", "neg", "eq", "gt", "lt", "and", "or", "not"
    }

    def __init__(self, lines):
        self.commands = []
        for line in lines:
            line = line.split("//", 1)[0].strip()
            if line:
                self.commands.append(line)
        self.index = -1
        self.current = None

    def has_more_commands(self):
        return self.index + 1 < len(self.commands)

    def advance(self):
        self.index += 1
        self.current = self.commands[self.index]

    def command_type(self):
        parts = self.current.split()
        cmd = parts[0]
        if cmd in self.ARITHMETIC_CMDS:
            return self.C_ARITHMETIC
        if cmd == "push":
            return self.C_PUSH
        if cmd == "pop":
            return self.C_POP
        if cmd == "label":
            return self.C_LABEL
        if cmd == "goto":
            return self.C_GOTO
        if cmd == "if-goto":
            return self.C_IF
        if cmd == "function":
            return self.C_FUNCTION
        if cmd == "call":
            return self.C_CALL
        if cmd == "return":
            return self.C_RETURN
        raise ValueError(f"Unknown command: {self.current}")

    def arg1(self):
        ctype = self.command_type()
        parts = self.current.split()
        if ctype == self.C_ARITHMETIC:
            return parts[0]
        if ctype == self.C_RETURN:
            raise ValueError("arg1 called on return")
        return parts[1]

    def arg2(self):
        ctype = self.command_type()
        if ctype not in (self.C_PUSH, self.C_POP, self.C_FUNCTION, self.C_CALL):
            raise ValueError("arg2 called on invalid command")
        parts = self.current.split()
        return int(parts[2])


class CodeWriter:
    SEGMENT_BASE = {
        "local": "LCL",
        "argument": "ARG",
        "this": "THIS",
        "that": "THAT",
    }

    def __init__(self):
        self.lines = []
        self.file_name = "Static"
        self.function_name = "null"
        self.label_counter = 0
        self.call_counter = 0

    def set_file_name(self, name):
        self.file_name = name

    def _emit(self, *instrs):
        for instr in instrs:
            self.lines.append(instr)

    def _unique(self, prefix):
        self.label_counter += 1
        return f"{prefix}${self.label_counter}"

    def _scoped_label(self, label):
        if self.function_name and self.function_name != "null":
            return f"{self.function_name}${label}"
        return label

    def write_init(self):
        self._emit(
            "// bootstrap",
            "@256",
            "D=A",
            "@SP",
            "M=D",
        )
        self.write_call("Sys.init", 0)

    def write_arithmetic(self, command):
        self._emit(f"// {command}")
        if command in ("add", "sub", "and", "or"):
            self._binary_op(command)
        elif command in ("neg", "not"):
            self._unary_op(command)
        elif command in ("eq", "gt", "lt"):
            self._compare_op(command)
        else:
            raise ValueError(f"Unknown arithmetic command: {command}")

    def _push_d(self):
        self._emit("@SP", "A=M", "M=D", "@SP", "M=M+1")

    def _pop_to_d(self):
        self._emit("@SP", "AM=M-1", "D=M")

    def _binary_op(self, command):
        ops = {"add": "D+M", "sub": "M-D", "and": "D&M", "or": "D|M"}
        self._pop_to_d()
        self._emit("@SP", "AM=M-1")
        self._emit(f"M={ops[command]}")
        self._emit("@SP", "M=M+1")

    def _unary_op(self, command):
        ops = {"neg": "-M", "not": "!M"}
        self._emit("@SP", "AM=M-1")
        self._emit(f"M={ops[command]}")
        self._emit("@SP", "M=M+1")

    def _compare_op(self, command):
        jump = {"eq": "JEQ", "gt": "JGT", "lt": "JLT"}[command]
        true_label = self._unique(f"{command.upper()}_TRUE")
        end_label = self._unique(f"{command.upper()}_END")
        self._pop_to_d()           # D = y
        self._emit("@SP", "AM=M-1")  # M = x
        self._emit("D=M-D")        # D = x - y
        self._emit(f"@{true_label}")
        self._emit(f"D;{jump}")
        self._emit("@SP", "A=M", "M=0")
        self._emit(f"@{end_label}", "0;JMP")
        self._emit(f"({true_label})")
        self._emit("@SP", "A=M", "M=-1")
        self._emit(f"({end_label})")
        self._emit("@SP", "M=M+1")

    def write_push_pop(self, command, segment, index):
        self._emit(f"// {command} {segment} {index}")
        if command == "push":
            self._write_push(segment, index)
        elif command == "pop":
            self._write_pop(segment, index)
        else:
            raise ValueError(f"Unknown push/pop command: {command}")

    def _write_push(self, segment, index):
        if segment == "constant":
            self._emit(f"@{index}", "D=A")
            self._push_d()
        elif segment in self.SEGMENT_BASE:
            base = self.SEGMENT_BASE[segment]
            self._emit(f"@{base}", "D=M", f"@{index}", "A=D+A", "D=M")
            self._push_d()
        elif segment == "temp":
            addr = 5 + index
            self._emit(f"@{addr}", "D=M")
            self._push_d()
        elif segment == "pointer":
            reg = "THIS" if index == 0 else "THAT"
            self._emit(f"@{reg}", "D=M")
            self._push_d()
        elif segment == "static":
            symbol = f"{self.file_name}.{index}"
            self._emit(f"@{symbol}", "D=M")
            self._push_d()
        else:
            raise ValueError(f"Unknown segment: {segment}")

    def _write_pop(self, segment, index):
        if segment in self.SEGMENT_BASE:
            base = self.SEGMENT_BASE[segment]
            self._emit(f"@{base}", "D=M", f"@{index}", "D=D+A", "@R13", "M=D")
            self._pop_to_d()
            self._emit("@R13", "A=M", "M=D")
        elif segment == "temp":
            addr = 5 + index
            self._pop_to_d()
            self._emit(f"@{addr}", "M=D")
        elif segment == "pointer":
            reg = "THIS" if index == 0 else "THAT"
            self._pop_to_d()
            self._emit(f"@{reg}", "M=D")
        elif segment == "static":
            symbol = f"{self.file_name}.{index}"
            self._pop_to_d()
            self._emit(f"@{symbol}", "M=D")
        else:
            raise ValueError(f"Unknown segment for pop: {segment}")

    def write_label(self, label):
        scoped = self._scoped_label(label)
        self._emit(f"// label {label}")
        self._emit(f"({scoped})")

    def write_goto(self, label):
        scoped = self._scoped_label(label)
        self._emit(f"// goto {label}")
        self._emit(f"@{scoped}", "0;JMP")

    def write_if(self, label):
        scoped = self._scoped_label(label)
        self._emit(f"// if-goto {label}")
        self._pop_to_d()
        self._emit(f"@{scoped}", "D;JNE")

    def write_function(self, function_name, num_locals):
        self.function_name = function_name
        self._emit(f"// function {function_name} {num_locals}")
        self._emit(f"({function_name})")
        for _ in range(num_locals):
            self._emit("@0", "D=A")
            self._push_d()

    def write_call(self, function_name, num_args):
        self.call_counter += 1
        return_label = f"{function_name}$ret.{self.call_counter}"
        self._emit(f"// call {function_name} {num_args}")
        # push return address
        self._emit(f"@{return_label}", "D=A")
        self._push_d()
        # push LCL, ARG, THIS, THAT
        for seg in ("LCL", "ARG", "THIS", "THAT"):
            self._emit(f"@{seg}", "D=M")
            self._push_d()
        # ARG = SP - 5 - num_args
        offset = 5 + num_args
        self._emit("@SP", "D=M", f"@{offset}", "D=D-A", "@ARG", "M=D")
        # LCL = SP
        self._emit("@SP", "D=M", "@LCL", "M=D")
        # goto function
        self._emit(f"@{function_name}", "0;JMP")
        # return label
        self._emit(f"({return_label})")

    def write_return(self):
        self._emit("// return")
        # FRAME = LCL (R13)
        self._emit("@LCL", "D=M", "@R13", "M=D")
        # RET = *(FRAME-5) (R14)
        self._emit("@5", "A=D-A", "D=M", "@R14", "M=D")
        # *ARG = pop()
        self._pop_to_d()
        self._emit("@ARG", "A=M", "M=D")
        # SP = ARG + 1
        self._emit("@ARG", "D=M+1", "@SP", "M=D")
        # restore THAT, THIS, ARG, LCL
        for i, seg in enumerate(("THAT", "THIS", "ARG", "LCL"), start=1):
            self._emit("@R13", "D=M", f"@{i}", "A=D-A", "D=M", f"@{seg}", "M=D")
        # goto RET
        self._emit("@R14", "A=M", "0;JMP")

    def output(self):
        return "\n".join(self.lines) + "\n"


def translate_file(vm_path, code_writer):
    with open(vm_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    base = os.path.splitext(os.path.basename(vm_path))[0]
    code_writer.set_file_name(base)
    parser = Parser(lines)
    while parser.has_more_commands():
        parser.advance()
        ctype = parser.command_type()
        if ctype == Parser.C_ARITHMETIC:
            code_writer.write_arithmetic(parser.arg1())
        elif ctype in (Parser.C_PUSH, Parser.C_POP):
            code_writer.write_push_pop(
                "push" if ctype == Parser.C_PUSH else "pop",
                parser.arg1(),
                parser.arg2(),
            )
        elif ctype == Parser.C_LABEL:
            code_writer.write_label(parser.arg1())
        elif ctype == Parser.C_GOTO:
            code_writer.write_goto(parser.arg1())
        elif ctype == Parser.C_IF:
            code_writer.write_if(parser.arg1())
        elif ctype == Parser.C_FUNCTION:
            code_writer.write_function(parser.arg1(), parser.arg2())
        elif ctype == Parser.C_CALL:
            code_writer.write_call(parser.arg1(), parser.arg2())
        elif ctype == Parser.C_RETURN:
            code_writer.write_return()
        else:
            raise ValueError(f"Unhandled command type: {ctype}")


def main():
    if len(sys.argv) != 2:
        print("Usage: VMTranslator <input.vm | directory>")
        sys.exit(1)

    input_path = os.path.abspath(sys.argv[1])
    if os.path.isdir(input_path):
        vm_files = sorted(
            os.path.join(input_path, f)
            for f in os.listdir(input_path)
            if f.endswith(".vm")
        )
        if not vm_files:
            print(f"No .vm files found in directory: {input_path}")
            sys.exit(1)
        out_path = os.path.join(input_path, os.path.basename(input_path) + ".asm")
        code_writer = CodeWriter()
        code_writer.write_init()
    elif os.path.isfile(input_path) and input_path.endswith(".vm"):
        vm_files = [input_path]
        out_path = os.path.splitext(input_path)[0] + ".asm"
        code_writer = CodeWriter()
    else:
        print(f"Invalid input path: {input_path}")
        sys.exit(1)

    for vm_file in vm_files:
        translate_file(vm_file, code_writer)

    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code_writer.output())

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
