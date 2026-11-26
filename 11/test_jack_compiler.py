#!/usr/bin/env python3
"""Test JackCompiler.py against the chapter 11 projects.

Checks:
  1. Compile every .jack in projects/11 and verify the XML tokens.
  2. Verify VM command syntax, labels, and functions.
  3. Run several projects in a mini VM with OS stubs and check results.

Output goes to projects/11/out; the original projects are not modified.
"""

import glob
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from JackCompiler import JackTokenizer, compile_file  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECTS = HERE
OUT = os.path.join(HERE, "out")

ARITHMETIC = {"add", "sub", "neg", "eq", "gt", "lt", "and", "or", "not"}
SEGMENTS = {"constant", "local", "argument", "this", "that", "temp", "pointer", "static"}
OS_CLASSES = {"Math", "String", "Array", "Memory", "Output", "Screen", "Keyboard", "Sys"}


def parse_vm(text):
    instructions = []
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) == 1:
            instructions.append((parts[0], None, None))
        elif len(parts) == 2:
            instructions.append((parts[0], parts[1], None))
        elif len(parts) == 3:
            instructions.append((parts[0], parts[1], int(parts[2])))
        else:
            raise AssertionError(f"bad VM line: {line}")
    return instructions


def check_xml(xml_text, source):
    root = ET.fromstring(xml_text)
    if root.tag != "class":
        raise AssertionError(f"root tag is {root.tag}, expected class")

    token_tags = {"keyword", "symbol", "identifier", "integerConstant", "stringConstant"}

    def leaves(element):
        if element.tag in token_tags:
            text = element.text or ""
            if text.startswith(" ") and text.endswith(" "):
                text = text[1:-1]
            yield element.tag, text
        else:
            for child in element:
                yield from leaves(child)

    actual = list(leaves(root))
    expected = [(token.kind, token.value) for token in JackTokenizer(source).tokens]
    if actual != expected:
        for i, (a, e) in enumerate(zip(actual, expected)):
            if a != e:
                raise AssertionError(f"token {i}: XML {a!r} != source {e!r}")
        raise AssertionError(f"token count: XML {len(actual)} != source {len(expected)}")
    return len(expected)


def check_vm(instructions):
    labels = set()
    gotos = []
    functions = {}
    current = None
    count = 0
    for cmd, arg1, arg2 in instructions:
        count += 1
        if cmd in ARITHMETIC:
            assert arg1 is None and arg2 is None, f"bad arithmetic: {cmd}"
        elif cmd in ("push", "pop"):
            assert arg1 in SEGMENTS and isinstance(arg2, int) and arg2 >= 0, \
                f"bad push/pop: {cmd} {arg1} {arg2}"
            if cmd == "push" and arg1 == "constant":
                assert arg2 <= 32767, f"constant out of range: {arg2}"
        elif cmd == "label":
            assert current is not None and isinstance(arg1, str)
            labels.add((current, arg1))
        elif cmd in ("goto", "if-goto"):
            gotos.append((current, arg1))
            assert arg2 is None
        elif cmd == "function":
            assert isinstance(arg2, int) and arg2 >= 0
            assert arg1 not in functions, f"duplicate function {arg1}"
            functions[arg1] = arg2
            current = arg1
        elif cmd == "call":
            assert isinstance(arg2, int) and arg2 >= 0, f"bad call: {arg1} {arg2}"
        elif cmd == "return":
            assert arg1 is None and arg2 is None
        else:
            raise AssertionError(f"unknown VM command: {cmd}")
    for func, label in gotos:
        assert (func, label) in labels, f"undefined label {label} in {func}"
    assert functions, "no function found"
    return count


def word(value):
    """轉成 16-bit two's complement 整數。"""
    return ((int(value) + 32768) % 65536) - 32768


class MiniVM:
    """只實作本測試需要的 VM 指令與 OS 服務。"""

    def __init__(self, vm_text):
        self.instructions = parse_vm(vm_text)
        func_body = {}
        label_pc = {}
        current = None
        for i, (cmd, arg1, arg2) in enumerate(self.instructions):
            if cmd == "function":
                current = arg1
                func_body[arg1] = (i + 1, arg2)
            elif cmd == "label":
                label_pc[(current, arg1)] = i
        self.func_body = func_body
        self.label_pc = label_pc
        self.ram = [0] * 24576
        self.sp = 256
        self.lcl = 0
        self.arg = 0
        self.this = 0  # RAM[3]
        self.that = 0  # RAM[4]
        self.frames = []
        self.pc = 0
        self.current_func = None
        self.statics = {}
        self.strings = {}
        self.next_heap = 2048
        self.output = []
        self.int_inputs = []
        self.key_inputs = []
        self.line_inputs = []
        self.halted = False
        self.steps = 0

    # RAM / stack helpers
    def read(self, address):
        if not 0 <= address < len(self.ram):
            raise RuntimeError(f"RAM address out of range: {address}")
        return self.ram[address]

    def write(self, address, value):
        if not 0 <= address < len(self.ram):
            raise RuntimeError(f"RAM address out of range: {address}")
        self.ram[address] = word(value)

    @property
    def sp(self):
        return self.ram[0]

    @sp.setter
    def sp(self, value):
        self.ram[0] = value

    @property
    def this(self):
        return self.ram[3]

    @this.setter
    def this(self, value):
        self.ram[3] = word(value)

    @property
    def that(self):
        return self.ram[4]

    @that.setter
    def that(self, value):
        self.ram[4] = word(value)

    def push(self, value):
        self.write(self.sp, value)
        self.sp += 1

    def pop(self):
        self.sp -= 1
        return self.read(self.sp)

    def segment_push(self, segment, index):
        if segment == "constant":
            return index
        if segment == "local":
            return self.read(self.lcl + index)
        if segment == "argument":
            return self.read(self.arg + index)
        if segment == "this":
            return self.read(self.this + index)
        if segment == "that":
            return self.read(self.that + index)
        if segment == "temp":
            assert 0 <= index < 8
            return self.read(5 + index)
        if segment == "pointer":
            assert 0 <= index < 2
            return self.read(3 + index)
        if segment == "static":
            cls = self.current_func.split(".")[0] if self.current_func else "?"
            return self.statics.get((cls, index), 0)
        raise RuntimeError(f"bad segment {segment}")

    def segment_pop(self, segment, index, value):
        if segment == "local":
            self.write(self.lcl + index, value)
        elif segment == "argument":
            self.write(self.arg + index, value)
        elif segment == "this":
            self.write(self.this + index, value)
        elif segment == "that":
            self.write(self.that + index, value)
        elif segment == "temp":
            assert 0 <= index < 8
            self.write(5 + index, value)
        elif segment == "pointer":
            assert 0 <= index < 2
            self.write(3 + index, value)
        elif segment == "static":
            cls = self.current_func.split(".")[0] if self.current_func else "?"
            self.statics[(cls, index)] = word(value)
        else:
            raise RuntimeError(f"bad pop segment {segment}")

    # OS stubs
    def alloc(self, size):
        address = self.next_heap
        self.next_heap += size
        if self.next_heap >= 16384:
            raise RuntimeError("heap overflow")
        return address

    def new_string(self, chars):
        address = self.alloc(max(len(chars) + 2, 2))
        self.strings[address] = [ord(c) & 0xFFFF for c in chars]
        return address

    def os_call(self, target, args):
        cls, _, name = target.partition(".")
        if cls == "Math":
            if name == "multiply":
                return args[0] * args[1]
            if name == "divide":
                if args[1] == 0:
                    raise RuntimeError("division by zero")
                sign = -1 if (args[0] < 0) != (args[1] < 0) else 1
                return sign * (abs(args[0]) // abs(args[1]))
            if name == "abs":
                return abs(args[0])
            if name == "max":
                return max(args[0], args[1])
            if name == "min":
                return min(args[0], args[1])
            if name == "sqrt":
                return int(abs(args[0]) ** 0.5)
        elif cls == "Array":
            if name == "new":
                return self.alloc(args[0])
            if name == "dispose":
                return None
        elif cls == "Memory":
            if name == "peek":
                return self.read(args[0])
            if name == "poke":
                self.write(args[0], args[1])
                return None
            if name == "alloc":
                return self.alloc(args[0])
            if name == "deAlloc":
                return None
        elif cls == "String":
            if name == "new":
                return self.new_string("")
            if name == "appendChar":
                self.strings.setdefault(args[0], []).append(word(args[1]))
                return args[0]
            if name == "length":
                return len(self.strings.get(args[0], []))
            if name == "charAt":
                return self.strings.get(args[0], [])[args[1]]
            if name == "setChar":
                self.strings[args[0]][args[1]] = word(args[2])
                return None
            if name == "eraseValue":
                self.strings[args[0]] = []
                return None
        elif cls == "Output":
            if name in ("printString", "printStringAt"):
                chars = self.strings.get(args[-1], [])
                self.output.append("".join(chr(c & 0xFFFF) for c in chars))
                return None
            if name in ("printInt", "printIntAt"):
                self.output.append(str(args[-1]))
                return None
            if name in ("println", "moveCursor", "printChar", "backSpace"):
                if name == "println":
                    self.output.append("\n")
                return None
        elif cls == "Screen":
            return None
        elif cls == "Keyboard":
            if name == "readInt":
                self.output.append("".join(chr(c & 0xFFFF)
                                           for c in self.strings.get(args[0], [])))
                return self.int_inputs.pop(0) if self.int_inputs else 0
            if name == "keyPressed":
                return self.key_inputs.pop(0) if self.key_inputs else 0
            if name == "readLine":
                text = self.line_inputs.pop(0) if self.line_inputs else ""
                return self.new_string(text)
        elif cls == "Sys":
            if name == "halt":
                self.halted = True
            elif name == "error":
                raise RuntimeError(f"Sys.error({args[0]})")
            return None
        raise RuntimeError(f"unimplemented OS call: {target}")

    # execution
    def call(self, target, n_args=0):
        if target not in self.func_body:
            raise RuntimeError(f"call to undefined function {target}")
        body_pc, n_locals = self.func_body[target]
        self.frames.append((self.pc + 1, self.lcl, self.arg, self.this,
                            self.that, self.current_func))
        self.push(0)  # return address placeholder
        for value in (self.lcl, self.arg, self.this, self.that):
            self.push(value)
        self.arg = self.sp - 5 - n_args
        self.lcl = self.sp
        for _ in range(n_locals):
            self.push(0)
        self.current_func = target
        self.pc = body_pc

    def run(self, max_steps=200000):
        while self.frames and not self.halted:
            self.steps += 1
            if self.steps > max_steps:
                raise RuntimeError(f"step limit exceeded ({max_steps})")
            cmd, arg1, arg2 = self.instructions[self.pc]
            if cmd in ARITHMETIC:
                if cmd in ("add", "sub", "and", "or", "eq", "gt", "lt"):
                    y = self.pop()
                    x = self.pop()
                    if cmd == "add":
                        result = x + y
                    elif cmd == "sub":
                        result = x - y
                    elif cmd == "and":
                        result = x & y
                    elif cmd == "or":
                        result = x | y
                    else:
                        result = -1 if {"eq": x == y, "gt": x > y,
                                        "lt": x < y}[cmd] else 0
                    self.push(result)
                elif cmd == "neg":
                    self.push(-self.pop())
                elif cmd == "not":
                    self.push(~self.pop())
                self.pc += 1
            elif cmd in ("push", "pop"):
                if cmd == "push":
                    self.push(self.segment_push(arg1, arg2))
                else:
                    self.segment_pop(arg1, arg2, self.pop())
                self.pc += 1
            elif cmd == "label":
                self.pc += 1
            elif cmd == "goto":
                self.pc = self.label_pc[(self.current_func, arg1)]
            elif cmd == "if-goto":
                value = self.pop()
                self.pc = (self.label_pc[(self.current_func, arg1)]
                           if value != 0 else self.pc + 1)
            elif cmd == "call":
                cls = arg1.split(".")[0]
                if cls in OS_CLASSES:
                    args = [self.pop() for _ in range(arg2)][::-1]
                    result = self.os_call(arg1, args)
                    self.push(0 if result is None else result)  # void 也放回傳值
                    self.pc += 1
                else:
                    # 呼叫使用者函式時，參數已經在堆疊上，直接交給 call 處理
                    self.call(arg1, arg2)
            elif cmd == "function":
                self.pc += 1
            elif cmd == "return":
                result = self.pop()
                self.write(self.arg, result)
                self.sp = self.arg + 1
                saved = self.frames.pop()
                self.pc, self.lcl, self.arg, self.this, self.that, self.current_func = saved
            else:
                raise RuntimeError(f"unknown command {cmd}")
        return "".join(self.output)


def run_project(name, setup=None, max_steps=200000):
    files = sorted(glob.glob(os.path.join(PROJECTS, name, "*.jack")))
    assert files, f"no jack files in {name}"
    vm_text = "\n".join(compile_file(path)[1] for path in files)
    vm = MiniVM(vm_text)
    if setup:
        setup(vm)
    vm.call("Main.main")
    return vm.run(max_steps), vm


def check_condition(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))
    return bool(condition)


def runtime_tests():
    print("\n[3] Running generated VM programs")
    ok = True

    output, _ = run_project("Seven")
    ok &= check_condition("Seven: 1 + 2 * 3 = 7", output == "7", repr(output))

    output, vm = run_project("ConvertToBin", lambda m: m.write(8000, 5))
    bits = vm.ram[8001:8017]
    expected = [(5 >> i) & 1 for i in range(16)]
    ok &= check_condition("ConvertToBin: RAM[8001..8016] holds bits of 5",
                         bits == expected, f"{bits} vs {expected}")

    def setup_average(m):
        m.int_inputs = [3, 10, 20, 30]  # 第一個輸入是數量
    output, _ = run_project("Average", setup_average)
    ok &= check_condition("Average: average is 20", "The average is 20" in output,
                          repr(output[-40:]))

    output, _ = run_project("ComplexArrays")
    expected_values = ["5", "40", "0", "77", "110"]
    ok &= check_condition("ComplexArrays: five expected values",
                          all(v in output for v in expected_values), repr(output))

    def setup_square(m):
        m.key_inputs = [81, 0]  # q, then key released
    output, _ = run_project("Square", setup_square, max_steps=50000)
    ok &= check_condition("Square: game runs and exits", True)

    def setup_pong(m):
        m.key_inputs = [140, 0]  # quit key, then key released
    output, _ = run_project("Pong", setup_pong, max_steps=50000)
    ok &= check_condition("Pong: game runs and exits", "Game Over" in output,
                          repr(output[-40:]))
    return ok


def main():
    print("[1] Compiling all chapter 11 projects")
    files = sorted(glob.glob(os.path.join(PROJECTS, "**", "*.jack"), recursive=True))
    assert files, f"no .jack files found in {PROJECTS}"
    all_ok = True
    for path in files:
        relative = os.path.relpath(path, PROJECTS)
        source = open(path, "r", encoding="utf-8-sig").read()
        xml_text, vm_text = compile_file(path)
        out_path = os.path.join(OUT, os.path.splitext(relative)[0])
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path + ".xml", "w", encoding="utf-8", newline="\n") as f:
            f.write(xml_text)
        with open(out_path + ".vm", "w", encoding="utf-8", newline="\n") as f:
            f.write(vm_text)
        try:
            tokens = check_xml(xml_text, source)
            instructions = parse_vm(vm_text)
            vm_count = check_vm(instructions)
            print(f"  [PASS] {relative}: {tokens} tokens, {vm_count} VM commands")
        except Exception as exc:
            all_ok = False
            print(f"  [FAIL] {relative}: {exc}")
    print(f"  total: {len(files)} files")

    if all_ok:
        try:
            all_ok &= runtime_tests()
        except Exception as exc:
            all_ok = False
            print(f"  [FAIL] runtime: {exc}")

    print("\nResult:", "ALL PASS" if all_ok else "FAILURES")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
