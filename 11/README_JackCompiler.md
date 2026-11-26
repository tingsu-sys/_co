# Jack 編譯器

`JackCompiler.py` 同時產生兩種輸出：

- `.xml`：第 11 章語法分析器的輸出（`JackTokenizer` + `CompilationEngine`）
- `.vm`：第 12 章的 VM 程式碼（含符號表、函式呼叫、陣列、字串、物件）

## 使用方式

```bat
cd "C:\tingsu\_co\11"

:: 單一檔案（輸出在原始檔旁邊）
JackCompiler.bat Seven\Main.jack

:: 整個資料夾（含子資料夾），輸出到 out\
python JackCompiler.py . --recursive --out out

:: 只要 XML 或只要 VM
python JackCompiler.py Seven\Main.jack --mode xml
python JackCompiler.py Seven\Main.jack --mode vm
```

## 測試

```bat
python test_jack_compiler.py
```

測試會：

1. 編譯 `11\` 下全部 11 個 `.jack` 檔，檢查 XML 是否合法、token 是否與原始檔一致，並檢查 VM 指令格式／標籤。
2. 用內建的迷你 VM 執行器（含 OS stub）實際執行 `Seven`、`ConvertToBin`、`Average`、`ComplexArrays`、`Square`、`Pong`，核對輸出與記憶體結果。

目前的執行結果：全部通過。

輸出檔案放在 `11\out`，第 11 章原始 `.jack` 檔不會被修改。
