import sys

# 預先定義的內建符號
SYMBOLS = {
    "SP": 0, "LCL": 1, "ARG": 2, "THIS": 3, "THAT": 4,
    "SCREEN": 16384, "KBD": 24576,
}
for i in range(16):
    SYMBOLS[f"R{i}"] = i

# C指令的對應對照表 (comp, dest, jump)
COMP_TABLE = {
    "0": "0101010", "1": "0111111", "-1": "0111010", "D": "0001100", "A": "0110000",
    "!D": "0001101", "!A": "0110001", "-D": "0001111", "-A": "0110011",
    "D+1": "0011111", "A+1": "0110111", "D-1": "0001110", "A-1": "0110010",
    "D+A": "0000010", "D-A": "0010011", "A-D": "0000111",
    "D&A": "0000000", "D|A": "0010101",
    # a=1 的情況 (M 運算)
    "M": "1110000", "!M": "1110001", "-M": "1110011", "M+1": "1110111",
    "M-1": "1110010", "D+M": "1000010", "D-M": "1010011", "M-D": "0000111",
    "D&M": "1000000", "D|M": "1010101"
}

DEST_TABLE = {
    "": "000", "M": "001", "D": "010", "MD": "011",
    "A": "100", "AM": "101", "AD": "110", "AMD": "111"
}

JUMP_TABLE = {
    "": "000", "JGT": "001", "JEQ": "010", "JGE": "011",
    "JLT": "100", "JNE": "101", "JLE": "110", "JMP": "111"
}

def clean_assembly(filename):
    """讀取檔案並過濾空白與註解"""
    clean_lines = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            # 移除註解與前後空白
            line = line.split('//')[0].strip()
            if line:
                clean_lines.append(line)
    return clean_lines

def assemble(filename):
    lines = clean_assembly(filename)
    
    # ---------------------------------------------
    # 第一階段：掃描所有標籤 (Labels) 並加入符號表
    # ---------------------------------------------
    rom_address = 0
    code_lines = []
    for line in lines:
        if line.startswith('(') and line.endswith(')'):
            symbol = line[1:-1]
            SYMBOLS[symbol] = rom_address
        else:
            code_lines.append(line)
            rom_address += 1

    # ---------------------------------------------
    # 第二階段：翻譯指令並處理變數 (Variables)
    # ---------------------------------------------
    ram_address = 16  # 使用者變數從 RAM 位址 16 開始配置
    binary_code = []

    for line in code_lines:
        if line.startswith('@'):
            # A-指令處理 (@value 或 @symbol)
            symbol = line[1:]
            if symbol.isdigit():
                val = int(symbol)
            else:
                if symbol not in SYMBOLS:
                    SYMBOLS[symbol] = ram_address
                    ram_address += 1
                val = SYMBOLS[symbol]
            # 轉換為 16-bit 二進位字串 (開頭為 0)
            binary_code.append(f"{val:016b}\n")
        else:
            # C-指令處理 (dest=comp;jump)
            dest = ""
            comp = ""
            jump = ""
            
            if '=' in line:
                dest, rest = line.split('=')
            else:
                rest = line
                
            if ';' in rest:
                comp, jump = rest.split(';')
            else:
                comp = rest

            c_bits = COMP_TABLE[comp]
            d_bits = DEST_TABLE[dest]
            j_bits = JUMP_TABLE[jump]
            
            # C-指令固定以 111 開頭
            binary_code.append(f"111{c_bits}{d_bits}{j_bits}\n")

    # 輸出為 .hack 檔案
    output_filename = filename.replace('.asm', '.hack')
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.writelines(binary_code)
    
    print(f"組譯成功！輸出檔案：{output_filename}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        assemble(sys.argv[1])
    else:
        print("使用方式: python assembler.py <filename.asm>")