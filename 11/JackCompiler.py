#!/usr/bin/env python3
"""Jack 語言編譯器。

同一份原始碼可輸出兩種結果：
  * .xml  -- 第 11 章 (語法分析) 的輸出格式
  * .vm   -- 第 12 章 (VM 程式碼產生) 的輸出格式

用法：
    JackCompiler.py <input.jack | directory> [--out DIR] [--mode both|xml|vm]
                    [--recursive]
"""

import argparse
import glob
import os
import sys

KEYWORDS = {
    "class", "constructor", "function", "method", "field", "static",
    "var", "int", "char", "boolean", "void", "true", "false", "null",
    "this", "let", "do", "if", "else", "while", "return",
}

SYMBOLS = set("{}()[].,;+-*/&|<>=~")
OP_SYMBOLS = {"+", "-", "*", "/", "&", "|", "<", ">", "="}
UNARY_OPS = {"-", "~"}
KEYWORD_CONSTANTS = {"true", "false", "null", "this"}
PRIMITIVE_TYPES = {"int", "char", "boolean", "void"}
KIND_SEGMENT = {
    "STATIC": "static",
    "FIELD": "this",
    "ARG": "argument",
    "VAR": "local",
}


def escape_xml(text):
    """把 XML 特殊字元轉成 entity。"""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


def strip_comments(source):
    """移除 // 與 /* */ 註解，但保留字串中的符號與換行。"""
    result = []
    i = 0
    n = len(source)
    state = "code"
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if state == "code":
            if ch == "/" and nxt == "/":
                state = "line"
                i += 2
            elif ch == "/" and nxt == "*":
                state = "block"
                i += 2
            elif ch == '"':
                result.append(ch)
                state = "string"
                i += 1
            else:
                result.append(ch)
                i += 1
        elif state == "line":
            if ch == "\n":
                result.append(ch)
                state = "code"
            i += 1
        elif state == "block":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
            else:
                if ch == "\n":
                    result.append(ch)
                i += 1
        else:  # string
            result.append(ch)
            if ch == '"':
                state = "code"
            i += 1
    return "".join(result)


class Token:
    def __init__(self, kind, value, line):
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self):
        return f"<{self.kind}:{self.value} @{self.line}>"


class JackTokenizer:
    """把 Jack 原始碼切成 token。"""

    def __init__(self, source):
        self.tokens = []
        self._tokenize(strip_comments(source))

    def _tokenize(self, text):
        i = 0
        line = 1
        n = len(text)
        while i < n:
            ch = text[i]
            if ch in " \t\r\n":
                if ch == "\n":
                    line += 1
                i += 1
                continue
            if ch == '"':
                end = text.find('"', i + 1)
                if end < 0:
                    raise SyntaxError(f"line {line}: unterminated string constant")
                value = text[i + 1:end]
                self.tokens.append(Token("stringConstant", value, line))
                line += text.count("\n", i, end + 1)
                i = end + 1
                continue
            if ch in SYMBOLS:
                self.tokens.append(Token("symbol", ch, line))
                i += 1
                continue
            if ch.isdigit():
                j = i
                while j < n and text[j].isdigit():
                    j += 1
                value = text[i:j]
                number = int(value)
                if number > 32767:
                    raise SyntaxError(f"line {line}: integer constant out of range: {value}")
                self.tokens.append(Token("integerConstant", value, line))
                i = j
                continue
            if ch.isalpha() or ch == "_":
                j = i
                while j < n and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                value = text[i:j]
                kind = "keyword" if value in KEYWORDS else "identifier"
                self.tokens.append(Token(kind, value, line))
                i = j
                continue
            raise SyntaxError(f"line {line}: unexpected character {ch!r}")


class SymbolTable:
    """class scope 與 subroutine scope 的符號表。"""

    def __init__(self):
        self.class_scope = {}
        self.subroutine_scope = {}
        self.counters = {"STATIC": 0, "FIELD": 0, "ARG": 0, "VAR": 0}

    def start_subroutine(self):
        self.subroutine_scope = {}
        self.counters["ARG"] = 0
        self.counters["VAR"] = 0

    def define(self, name, var_type, kind):
        table = self.subroutine_scope if kind in ("ARG", "VAR") else self.class_scope
        table[name] = (var_type, kind, self.counters[kind])
        self.counters[kind] += 1

    def lookup(self, name):
        if name in self.subroutine_scope:
            return self.subroutine_scope[name]
        if name in self.class_scope:
            return self.class_scope[name]
        return None

    def kind_of(self, name):
        entry = self.lookup(name)
        return entry[1] if entry else None

    def type_of(self, name):
        entry = self.lookup(name)
        return entry[0] if entry else None

    def index_of(self, name):
        entry = self.lookup(name)
        return entry[2] if entry else None

    def count(self, kind):
        return self.counters[kind]


class VMWriter:
    def __init__(self):
        self.lines = []

    def write_push(self, segment, index):
        self.lines.append(f"push {segment} {index}")

    def write_pop(self, segment, index):
        self.lines.append(f"pop {segment} {index}")

    def write_arithmetic(self, command):
        self.lines.append(command)

    def write_label(self, label):
        self.lines.append(f"label {label}")

    def write_goto(self, label):
        self.lines.append(f"goto {label}")

    def write_if(self, label):
        self.lines.append(f"if-goto {label}")

    def write_call(self, name, n_args):
        self.lines.append(f"call {name} {n_args}")

    def write_function(self, name, n_locals):
        self.lines.append(f"function {name} {n_locals}")

    def write_return(self):
        self.lines.append("return")


class CompilationEngine:
    """遞歸下降剖析器，同時產生 XML 與 VM 程式碼。"""

    def __init__(self, source):
        self.tokens = JackTokenizer(source).tokens
        self.index = 0
        self.xml = []
        self.vm = VMWriter()
        self.symbols = SymbolTable()
        self.class_name = ""
        self.subroutine_kinds = {}
        self.label_id = 0
        self._scan_subroutine_kinds()

    def _scan_subroutine_kinds(self):
        """先掃一遍，讓呼叫寫在定義之前的 method 也能被正確辨識。"""
        for i in range(len(self.tokens) - 2):
            token = self.tokens[i]
            if token.kind == "keyword" and token.value in ("constructor", "function", "method"):
                name = self.tokens[i + 2]
                if name.kind == "identifier":
                    self.subroutine_kinds[name.value] = token.value

    # ---- token 基本操作 ----

    def _peek(self, offset=0):
        pos = self.index + offset
        return self.tokens[pos] if pos < len(self.tokens) else None

    def _take(self):
        token = self._peek()
        if token is None:
            raise SyntaxError("unexpected end of file")
        self.index += 1
        self.xml.append(f"<{token.kind}> {escape_xml(token.value)} </{token.kind}>")
        return token

    def _expect(self, kind=None, value=None):
        token = self._peek()
        if token is None:
            raise SyntaxError("unexpected end of file")
        if kind is not None and token.kind != kind:
            raise SyntaxError(
                f"line {token.line}: expected {kind}, got {token.kind} {token.value!r}")
        if value is not None and token.value != value:
            raise SyntaxError(
                f"line {token.line}: expected {value!r}, got {token.value!r}")
        return self._take()

    def _expect_keyword(self, value):
        return self._expect("keyword", value)

    def _expect_symbol(self, value):
        return self._expect("symbol", value)

    def _expect_identifier(self):
        return self._expect("identifier")

    def _at(self, kind, value):
        token = self._peek()
        return token is not None and token.kind == kind and token.value == value

    def _open(self, tag):
        self.xml.append(f"<{tag}>")

    def _close(self, tag):
        self.xml.append(f"</{tag}>")

    def _new_label(self, prefix):
        self.label_id += 1
        return f"{prefix}_{self.label_id}"

    def _segment_of(self, name):
        entry = self.symbols.lookup(name)
        if entry is None:
            token = self._peek()
            line = token.line if token else "?"
            raise SyntaxError(f"line {line}: undeclared variable {name!r}")
        return KIND_SEGMENT[entry[1]], entry[2]

    # ---- 編譯入口 ----

    def compile(self):
        self.compile_class()
        if self.index != len(self.tokens):
            token = self._peek()
            raise SyntaxError(f"line {token.line}: unexpected token {token.value!r}")
        return "\n".join(self.xml) + "\n", "\n".join(self.vm.lines) + "\n"

    def compile_class(self):
        self._open("class")
        self._expect_keyword("class")
        self.class_name = self._expect_identifier().value
        self._expect_symbol("{")
        while self._at("keyword", "static") or self._at("keyword", "field"):
            self.compile_class_var_dec()
        while (self._peek() is not None and self._peek().kind == "keyword"
               and self._peek().value in ("constructor", "function", "method")):
            self.compile_subroutine()
        self._expect_symbol("}")
        self._close("class")

    def compile_type(self):
        token = self._peek()
        if token is None:
            raise SyntaxError("expected type, got end of file")
        if token.kind == "keyword" and token.value in PRIMITIVE_TYPES:
            return self._take().value
        if token.kind == "identifier":
            return self._take().value
        raise SyntaxError(f"line {token.line}: expected type, got {token.value!r}")

    def compile_class_var_dec(self):
        self._open("classVarDec")
        kind = self._take().value.upper()
        var_type = self.compile_type()
        name = self._expect_identifier().value
        self.symbols.define(name, var_type, kind)
        while self._at("symbol", ","):
            self._expect_symbol(",")
            name = self._expect_identifier().value
            self.symbols.define(name, var_type, kind)
        self._expect_symbol(";")
        self._close("classVarDec")

    def _count_locals(self):
        """偷看 varDec 以取得 local 數量，之後把 index 還原。"""
        saved = self.index
        count = 0
        while self._peek() is not None and self._at("keyword", "var"):
            self.index += 1  # var
            if self._peek() is None:
                break
            self.index += 1  # type
            while True:
                if self._peek() is None:
                    break
                self.index += 1  # variable name
                count += 1
                if self._at("symbol", ","):
                    self.index += 1
                    continue
                if self._at("symbol", ";"):
                    self.index += 1
                    break
                break
        self.index = saved
        return count

    def compile_subroutine(self):
        self._open("subroutineDec")
        kind = self._take().value
        return_type = self.compile_type()
        name = self._expect_identifier().value
        self._expect_symbol("(")
        self.symbols.start_subroutine()
        if kind == "method":
            self.symbols.define("this", self.class_name, "ARG")

        self._open("parameterList")
        if not self._at("symbol", ")"):
            while True:
                param_type = self.compile_type()
                param_name = self._expect_identifier().value
                self.symbols.define(param_name, param_type, "ARG")
                if not self._at("symbol", ","):
                    break
                self._expect_symbol(",")
        self._close("parameterList")
        self._expect_symbol(")")

        self._open("subroutineBody")
        self._expect_symbol("{")
        n_locals = self._count_locals()
        full_name = f"{self.class_name}.{name}"
        self.vm.write_function(full_name, n_locals)
        if kind == "constructor":
            self.vm.write_push("constant", self.symbols.count("FIELD"))
            self.vm.write_call("Memory.alloc", 1)
            self.vm.write_pop("pointer", 0)
        elif kind == "method":
            self.vm.write_push("argument", 0)
            self.vm.write_pop("pointer", 0)

        while self._at("keyword", "var"):
            self.compile_var_dec()
        self.compile_statements()
        self._expect_symbol("}")
        self._close("subroutineBody")
        self._close("subroutineDec")

    def compile_var_dec(self):
        self._open("varDec")
        self._expect_keyword("var")
        var_type = self.compile_type()
        name = self._expect_identifier().value
        self.symbols.define(name, var_type, "VAR")
        while self._at("symbol", ","):
            self._expect_symbol(",")
            name = self._expect_identifier().value
            self.symbols.define(name, var_type, "VAR")
        self._expect_symbol(";")
        self._close("varDec")

    # ---- statements ----

    STATEMENTS = {"let", "if", "while", "do", "return"}

    def compile_statements(self):
        self._open("statements")
        while (self._peek() is not None and self._peek().kind == "keyword"
               and self._peek().value in self.STATEMENTS):
            keyword = self._peek().value
            if keyword == "let":
                self.compile_let()
            elif keyword == "if":
                self.compile_if()
            elif keyword == "while":
                self.compile_while()
            elif keyword == "do":
                self.compile_do()
            else:
                self.compile_return()
        self._close("statements")

    def compile_let(self):
        self._open("letStatement")
        self._expect_keyword("let")
        name = self._expect_identifier().value
        segment, index = self._segment_of(name)
        is_array = self._at("symbol", "[")
        if is_array:
            self._expect_symbol("[")
            self.vm.write_push(segment, index)  # 先推入基底位址
            self.compile_expression()
            self._expect_symbol("]")
            self.vm.write_arithmetic("add")
        self._expect_symbol("=")
        self.compile_expression()
        self._expect_symbol(";")
        if is_array:
            self.vm.write_pop("temp", 0)
            self.vm.write_pop("pointer", 1)
            self.vm.write_push("temp", 0)
            self.vm.write_pop("that", 0)
        else:
            self.vm.write_pop(segment, index)
        self._close("letStatement")

    def compile_if(self):
        self._open("ifStatement")
        self._expect_keyword("if")
        self._expect_symbol("(")
        self.compile_expression()
        self._expect_symbol(")")
        self.vm.write_arithmetic("not")
        label = self._new_label("IF")
        self.vm.write_if(f"{label}_ELSE")
        self._expect_symbol("{")
        self.compile_statements()
        self._expect_symbol("}")
        self.vm.write_goto(f"{label}_END")
        self.vm.write_label(f"{label}_ELSE")
        if self._at("keyword", "else"):
            self._expect_keyword("else")
            self._expect_symbol("{")
            self.compile_statements()
            self._expect_symbol("}")
        self.vm.write_label(f"{label}_END")
        self._close("ifStatement")

    def compile_while(self):
        label = self._new_label("WHILE")
        self._open("whileStatement")
        self._expect_keyword("while")
        self.vm.write_label(f"{label}_EXP")
        self._expect_symbol("(")
        self.compile_expression()
        self._expect_symbol(")")
        self.vm.write_arithmetic("not")
        self.vm.write_if(f"{label}_END")
        self._expect_symbol("{")
        self.compile_statements()
        self._expect_symbol("}")
        self.vm.write_goto(f"{label}_EXP")
        self.vm.write_label(f"{label}_END")
        self._close("whileStatement")

    def compile_do(self):
        self._open("doStatement")
        self._expect_keyword("do")
        self.compile_subroutine_call()
        self._expect_symbol(";")
        self.vm.write_pop("temp", 0)  # 捨棄回傳值
        self._close("doStatement")

    def compile_return(self):
        self._open("returnStatement")
        self._expect_keyword("return")
        if self._at("symbol", ";"):
            self.vm.write_push("constant", 0)  # void 也要放回傳值
        else:
            self.compile_expression()
        self._expect_symbol(";")
        self.vm.write_return()
        self._close("returnStatement")

    # ---- expressions ----

    def compile_expression(self):
        self._open("expression")
        self.compile_term()
        while self._peek() is not None and self._peek().kind == "symbol" \
                and self._peek().value in OP_SYMBOLS:
            op = self._take().value
            self.compile_term()
            self._write_op(op)
        self._close("expression")

    def _write_op(self, op):
        if op == "+":
            self.vm.write_arithmetic("add")
        elif op == "-":
            self.vm.write_arithmetic("sub")
        elif op == "&":
            self.vm.write_arithmetic("and")
        elif op == "|":
            self.vm.write_arithmetic("or")
        elif op == "<":
            self.vm.write_arithmetic("lt")
        elif op == ">":
            self.vm.write_arithmetic("gt")
        elif op == "=":
            self.vm.write_arithmetic("eq")
        elif op == "*":
            self.vm.write_call("Math.multiply", 2)
        elif op == "/":
            self.vm.write_call("Math.divide", 2)
        else:
            raise SyntaxError(f"unknown operator {op!r}")

    def compile_term(self):
        self._open("term")
        token = self._peek()
        if token is None:
            raise SyntaxError("expected term, got end of file")

        if token.kind == "integerConstant":
            self.vm.write_push("constant", int(self._take().value))
        elif token.kind == "stringConstant":
            value = self._take().value
            self.vm.write_push("constant", len(value))
            self.vm.write_call("String.new", 1)
            for ch in value:
                self.vm.write_push("constant", ord(ch))
                self.vm.write_call("String.appendChar", 2)
        elif token.kind == "keyword" and token.value in KEYWORD_CONSTANTS:
            keyword = self._take().value
            if keyword == "true":
                self.vm.write_push("constant", 0)
                self.vm.write_arithmetic("not")
            elif keyword in ("false", "null"):
                self.vm.write_push("constant", 0)
            else:  # this
                self.vm.write_push("pointer", 0)
        elif token.kind == "symbol" and token.value == "(":
            self._expect_symbol("(")
            self.compile_expression()
            self._expect_symbol(")")
        elif token.kind == "symbol" and token.value in UNARY_OPS:
            op = self._take().value
            self.compile_term()
            self.vm.write_arithmetic("neg" if op == "-" else "not")
        elif token.kind == "identifier":
            next_token = self._peek(1)
            if next_token is not None and next_token.value in (".", "("):
                self.compile_subroutine_call()
            elif next_token is not None and next_token.value == "[":
                name = self._expect_identifier().value
                segment, index = self._segment_of(name)
                self._expect_symbol("[")
                self.compile_expression()
                self._expect_symbol("]")
                self.vm.write_push(segment, index)
                self.vm.write_arithmetic("add")
                self.vm.write_pop("pointer", 1)
                self.vm.write_push("that", 0)
            else:
                name = self._expect_identifier().value
                segment, index = self._segment_of(name)
                self.vm.write_push(segment, index)
        else:
            raise SyntaxError(f"line {token.line}: unexpected term {token.value!r}")
        self._close("term")

    def compile_subroutine_call(self):
        self._open("subroutineCall")
        first = self._expect_identifier().value
        n_base_args = 0
        if self._at("symbol", "."):
            self._expect_symbol(".")
            second = self._expect_identifier().value
            entry = self.symbols.lookup(first)
            if entry is None:
                target = f"{first}.{second}"
            else:
                var_type, kind, index = entry
                self.vm.write_push(KIND_SEGMENT[kind], index)
                target = f"{var_type}.{second}"
                n_base_args = 1
        else:
            target = f"{self.class_name}.{first}"
            if self.subroutine_kinds.get(first) in ("method", "constructor"):
                self.vm.write_push("pointer", 0)
                n_base_args = 1
        self._expect_symbol("(")
        n_args = self.compile_expression_list()
        self._expect_symbol(")")
        self.vm.write_call(target, n_base_args + n_args)
        self._close("subroutineCall")

    def compile_expression_list(self):
        self._open("expressionList")
        count = 0
        if not self._at("symbol", ")"):
            while True:
                self.compile_expression()
                count += 1
                if not self._at("symbol", ","):
                    break
                self._expect_symbol(",")
        self._close("expressionList")
        return count


def compile_file(path):
    """回傳 (xml_text, vm_text)。"""
    with open(path, "r", encoding="utf-8-sig") as f:
        source = f.read()
    return CompilationEngine(source).compile()


def find_jack_files(input_path, recursive=False):
    if os.path.isfile(input_path):
        if not input_path.lower().endswith(".jack"):
            raise ValueError(f"not a .jack file: {input_path}")
        return [input_path]
    if not os.path.isdir(input_path):
        raise ValueError(f"input not found: {input_path}")
    pattern = os.path.join(input_path, "**", "*.jack") if recursive \
        else os.path.join(input_path, "*.jack")
    return sorted(glob.glob(pattern, recursive=recursive))


def main():
    parser = argparse.ArgumentParser(description="Jack compiler (XML + VM)")
    parser.add_argument("input", help=".jack file or a directory of .jack files")
    parser.add_argument("--out", help="output directory (default: next to source)")
    parser.add_argument("--mode", choices=("both", "xml", "vm"), default="both")
    parser.add_argument("--recursive", action="store_true",
                        help="also process .jack files in subdirectories")
    args = parser.parse_args()

    try:
        files = find_jack_files(args.input, args.recursive)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    if not files:
        print(f"No .jack files found in: {args.input}", file=sys.stderr)
        sys.exit(1)

    input_dir = args.input if os.path.isdir(args.input) else os.path.dirname(args.input)
    for path in files:
        try:
            xml_text, vm_text = compile_file(path)
        except SyntaxError as exc:
            print(f"Error compiling {path}: {exc}", file=sys.stderr)
            sys.exit(1)
        base = os.path.splitext(os.path.basename(path))[0]
        if args.out:
            relative = os.path.relpath(os.path.dirname(path), input_dir)
            out_dir = args.out if relative == "." else os.path.join(args.out, relative)
        else:
            out_dir = os.path.dirname(path)
        os.makedirs(out_dir, exist_ok=True)
        if args.mode in ("both", "xml"):
            with open(os.path.join(out_dir, base + ".xml"), "w",
                      encoding="utf-8", newline="\n") as f:
                f.write(xml_text)
        if args.mode in ("both", "vm"):
            with open(os.path.join(out_dir, base + ".vm"), "w",
                      encoding="utf-8", newline="\n") as f:
                f.write(vm_text)
        print(f"Compiled {path} -> {out_dir}/{base}")


if __name__ == "__main__":
    main()
