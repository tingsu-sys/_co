一、 什麼是 IC 設計的 EDA（電子設計自動化）？
EDA（Electronic Design Automation，電子設計自動化） 是指利用電腦軟體與硬體系統來協助工程師進行半導體與積體電路（IC）晶片設計、模擬、驗證、合成與製造準備的技術。
在現代半導體產業中，單顆先進晶片往往包含數十億甚至上百億個電晶體，透過人工繪製電路圖或肉眼檢查早已無法實現。因此，EDA 工具扮演了串接「高階邏輯構想」與「實體矽晶片製造」的關鍵橋樑。
根據 EDA 電子書 與頂尖學府如 康乃爾大學 IC 設計課程 (ECE 5745) 的架構，完整的 IC 設計流程（RTL to GDSII）主要包含以下核心環節：
高階行為描述與模擬（Behavioral Simulation）：使用硬體描述語言（HDL）定義電路邏輯，並透過測試平台（Testbench）驗證功能正確性。
邏輯合成（Logic Synthesis）：將抽象的高階語言轉換為基於特定製程庫（PDK）的標準閘級網表（Gate-level Netlist）。
佈局與繞線（Place & Route, P&R）：決定各個邏輯元件在晶片實體空間中的位置，並完成複雜的金屬導線連結。
實體驗證與時序分析（Physical Verification & STA）：確保晶片符合製造廠的幾何設計規則（DRC）、網表一致性（LVS）以及最高工作時脈的時序要求。
二、 開源與 AI 輔助 EDA 工具之應用與體驗
為了降低 IC 設計的門檻並推動開源硬體發展，近年來出現了許多結合現代網頁技術與人工智慧的輕量化 EDA 工具。本次作業參考並探討了以下兩個重要專案：
1. AI 自製 EDA 專案 (Veryl2Chip)
專案網址：GitHub - veryl2chip | 線上使用環境
心得與觀察：
新型硬體描述語言 Veryl：傳統的 Verilog 語法較為繁瑣且容易出錯。Veryl 借鏡了現代程式語言（如 Rust）的型別系統與模組化設計，讓硬體描述更具結構性與可讀性。
AI 與 EDA 的結合：透過線上環境，可以體驗如何利用 AI 與自動化編譯流程，將高階的 Veryl 語法快速轉換、合成至底層的電路網表，展現了開源 EDA 工具在教學與快速原型開發上的巨大潛力。
2. Nand2tetris 網頁 HDL 模擬專案 (Hack Computer)
專案網址：GitHub - hack-computer | 線上 HDL 模擬器
心得與觀察：
由底至上的硬體建構：Nand2tetris 專案帶領學習者從最基本的反相閘/反及閘（Nand Gate）出發，逐步建構出多工器（Mux）、算術邏輯單元（ALU）、暫存器組（RAM）乃至完整的 Hack CPU 與電腦系統。
波形與控制訊號除錯：透過網頁端的 HDL 模擬器，能夠直觀地觀察不同控制訊號（Control Lines）與時脈（Clock）觸發下，資料在暫存器與資料匯流排間的流動狀態。這對於理解「組合邏輯」與「循序邏輯」的差異至關重要。
三、 結論
透過本次作業的文獻研讀與線上 EDA 工具的操作體驗，我們深刻體會到 EDA 在現代數位系統設計中不可動搖的地位。無論是透過 Nand2tetris 理解從基礎邏輯閘到計算機架構的建構過程，還是利用 Veryl2Chip 探索現代硬體描述語言與 AI 輔助工具的便利性，都讓我們對 IC 設計從抽象程式碼落實到實體硬體的全貌有了更清晰的認知。
四、 參考資料與連結
AI 自製 EDA (Veryl2Chip)
GitHub 專案：https://github.com/ccc-eda/veryl2chip/
線上操作環境：https://ccc-eda.github.io/veryl2chip/web/dist/index.html
Nand2tetris 網頁專案 (Hack Computer)
GitHub 專案：https://github.com/ccc-js/hack-computer
線上 HDL 模擬器：https://ccc-js.github.io/hack-computer/dist/hdl.html
EDA 電子書：https://github.com/ccc-eda/eda-books/tree/main/book
康乃爾大學 IC 設計課程講義 (ECE 5745)：https://www.csl.cornell.edu/courses/ece5745/handouts.html


