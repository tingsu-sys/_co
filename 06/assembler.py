import sys
import os

class SymbolTable:
    def __init__(self):
        # 初始化預定義符號
        self.table = {
            "SP": 0, "LCL": 1, "ARG": 2, "THIS": 3, "THAT": 4,
            "SCREEN": 16384, "KBD": 24576
        }
        for i in range(16):
            self.table[f"R{i}"] = i

    def add_entry(self, symbol, address):
        self.table[symbol] = address

    def contains(self, symbol):
        return symbol in self.table

    def get_address(self, symbol):
        return self.table[symbol]


class Parser:
    def __init__(self, input_file):
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 清理註解與空白行
        self.commands = []
        for line in lines:
            # 移除註解
            line = line.split('//')[0].strip()
            if line:
                self.commands.append(line)
        
        self.current_index = -1
        self.current_command = ""

    def has_more_commands(self):
        return self.current_index + 1 < len(self.commands)

    def advance(self):
        self.current_index += 1
        self.current_command = self.commands[self.current_index]

    def command_type(self):
        if self.current_command.startswith('@'):
            return "A_COMMAND"
        elif self.current_command.startswith('('):
            return "L_COMMAND"
        else:
            return "C_COMMAND"

    def symbol(self):
        cmd = self.current_command
        if cmd.startswith('@'):
            return cmd[1:]
        elif cmd.startswith('('):
            return cmd[1:-1]
        return None

    def dest(self):
        cmd = self.current_command
        if '=' in cmd:
            return cmd.split('=')[0]
        return "null"

    def comp(self):
        cmd = self.current_command
        # 處理 dest=comp;jump 或 dest=comp 或 comp;jump
        if '=' in cmd:
            cmd = cmd.split('=')[1]
        if ';' in cmd:
            cmd = cmd.split(';')[0]
        return cmd

    def jump(self):
        cmd = self.current_command
        if ';' in cmd:
            return cmd.split(';')[1]
        return "null"


class Code:
    @staticmethod
    def dest(mnemonic):
        table = {
            "null": "000", "M": "001", "D": "010", "MD": "011",
            "A": "100", "AM": "101", "AD": "110", "AMD": "111"
        }
        return table.get(mnemonic, "000")

    @staticmethod
    def comp(mnemonic):
        table = {
            "0":   "0101010", "1":   "0111111", "-1":  "0111010",
            "D":   "0001100", "A":   "0110000", "!D":  "0001101",
            "!A":  "0110001", "-D":  "0001111", "-A":  "0110011",
            "D+1": "0011111", "A+1": "0110111", "D-1": "0001110",
            "A-1": "0110010", "D+A": "0000010", "D-A": "0010011",
            "A-D": "0000111", "D&A": "0000000", "D|A": "0010101",
            # 以 M 開頭的對應運算（a 位元為 1）
            "M":   "1110000", "!M":  "1110001", "-M":  "1110011",
            "M+1": "1110111", "M-1": "1110010", "D+M": "1000010",
            "D-M": "1010011", "M-D": "1000111", "D&M": "1000000",
            "D|M": "1010101"
        }
        return table.get(mnemonic, "0000000")

    @staticmethod
    def jump(mnemonic):
        table = {
            "null": "000", "JGT": "001", "JEQ": "010", "JGE": "011",
            "JLT": "100", "JNE": "101", "JLE": "110", "JMP": "111"
        }
        return table.get(mnemonic, "000")


def assemble(input_file):
    parser = Parser(input_file)
    symbol_table = SymbolTable()
    
    # === 第一次掃描：處理所有標籤 (Labels) ===
    rom_address = 0
    while parser.has_more_commands():
        parser.advance()
        c_type = parser.command_type()
        if c_type == "L_COMMAND":
            symbol = parser.symbol()
            if not symbol_table.contains(symbol):
                symbol_table.add_entry(symbol, rom_address)
        else:
            rom_address += 1

    # === 第二次掃描：處理變數與指令轉譯 ===
    parser = Parser(input_file)  # 重新建立 Parser 重頭讀取
    next_available_ram = 16      # 變數從 RAM 位址 16 開始配置
    binary_output = []

    while parser.has_more_commands():
        parser.advance()
        c_type = parser.command_type()

        if c_type == "A_COMMAND":
            symbol = parser.symbol()
            # 判斷是數字還是符號/變數
            if symbol.isdigit():
                address = int(symbol)
            else:
                if not symbol_table.contains(symbol):
                    symbol_table.add_entry(symbol, next_available_ram)
                    next_available_ram += 1
                address = symbol_table.get_address(symbol)
            
            # 轉為 15 位元二進位並加上開頭的 0
            binary_output.append(format(address, '016b'))

        elif c_type == "C_COMMAND":
            dest_mnemonic = parser.dest()
            comp_mnemonic = parser.comp()
            jump_mnemonic = parser.jump()

            dest_bits = Code.dest(dest_mnemonic)
            comp_bits = Code.comp(comp_mnemonic)
            jump_bits = Code.jump(jump_mnemonic)

            # C 指令格式：111 + a/comp(7bits) + dest(3bits) + jump(3bits)
            instruction = "111" + comp_bits + dest_bits + jump_bits
            binary_output.append(instruction)

        # L_COMMAND 在第一次掃描已經處理完畢，此處略過

    # 寫入輸出檔案 (.hack)
    output_file = os.path.splitext(input_file)[0] + ".hack"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(binary_output) + '\n')
    
    print(f"組譯成功！輸出檔案：{output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方式: python assembler.py <filename.asm>")
    else:
        assemble(sys.argv[1])