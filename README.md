# news-to-db

把 ProQuest 匯出的報紙 `.txt`(Financial Times、Wall Street Journal)拆成欄位,寫入資料庫。可用 `--db` 選擇 MongoDB(預設)、SQLite 或兩者都寫。

## 環境安裝

```bash
mamba env create -f environment.yml
mamba activate NSTC-115-2
```

環境名稱為 `NSTC-115-2`(Python 3.11 + pymongo)。不想 activate 的話,在指令前加 `mamba run -n NSTC-115-2` 即可。

> Windows 上如果專案路徑含中文,`mamba env create -f` 可能讀不到 YAML,把 `environment.yml` 複製到純英文路徑再建即可。

## 資料夾結構

```
Data/
  FT/        Financial Times 的 ProQuest txt
  WSJ/       Wall Street Journal 的 ProQuest txt
  sqlite/    產生的資料庫 news.db(自動建立)
```

- 資料夾名稱 **`Data` 要大寫**。Linux 檔案系統分大小寫,`data/` 和 `Data/` 是不同資料夾。
- `Data/` 已在 `.gitignore`,原始新聞全文與資料庫不會被 commit。
- txt 檔名不影響解析(例如 `ProQuestDocuments-1996-05-31-第一頁.txt`),程式只看副檔名 `.txt`,日期等資訊都從檔案內容讀取。

## 使用方式

```bash
python main.py [路徑 ...] [選項]
```

`路徑` 可以是資料夾、單一檔案,或帶萬用字元的檔名,可混用、可給多個。

| 想做的事 | 指令 |
|---|---|
| 掃描預設的 `Data/FT` 和 `Data/WSJ` | `python main.py` |
| 整個資料夾的所有 txt(含子資料夾) | `python main.py Data/FT/1996` |
| 多個資料夾 | `python main.py Data/FT Data/WSJ` |
| 單一檔案 | `python main.py "Data/FT/ProQuestDocuments-1996-05-31-第一頁.txt"` |
| 只跑某一年 | `python main.py "Data/FT/ProQuestDocuments-1996-*.txt" "Data/WSJ/ProQuestDocuments-1996-*.txt"` |
| 寫入 SQLite(預設是 MongoDB) | `python main.py Data/FT --db sqlite` |
| 同時寫入 MongoDB 和 SQLite | `python main.py Data/FT Data/WSJ --db both` |

注意:
- 萬用字元(`*`、`?`、`[`)要用**引號**包住,由程式自己展開。PowerShell / cmd 不會替程式展開,Linux 的 shell 則會提前展開並可能造成錯誤。
- 路徑可以是相對或絕對路徑。
- 沒有找到任何 txt 時會印 `No .txt files found to parse.` 並以代碼 1 結束。

### 選項

| 選項 | 說明 | 預設 |
|---|---|---|
| `--db` | 目標資料庫:`mongo`、`sqlite`、`both` | `mongo` |
| `--sqlite-path` | 輸出的 SQLite 檔案路徑(`--db` 含 sqlite 時使用) | `Data/sqlite/news.db` |
| `--mongo-uri` | MongoDB 連線字串(`--db` 含 mongo 時使用) | `$MONGODB_URI`,否則 `mongodb://localhost:27017` |
| `--mongo-db` | MongoDB 資料庫名稱 | `115_Text_Project` |

預設會寫 MongoDB,所以執行前 MongoDB 要先啟動。連不上時會印 `MongoDB: could not reach ...`、不寫入任何資料並以代碼 1 結束;`--db both` 時 Mongo 失敗不影響 SQLite 寫入。

### MongoDB 的 collection 對應

依檔案所在的來源資料夾決定寫入哪個 collection(資料庫預設為 `115_Text_Project`):

| 資料夾 | collection |
|---|---|
| `Data/FT/...`(含子資料夾) | `FinancialTimes` |
| `Data/WSJ/...`(含子資料夾) | `WSJ` |

- 判斷方式是檔案路徑中最靠近檔案的名為 `FT` 或 `WSJ` 的資料夾。不在這兩個資料夾底下的 txt 不會寫入 MongoDB,會印警告並以代碼 1 結束(SQLite 不受影響)。
- 程式不會建立或修改索引,只用 `proquest_id` 當 `_id` 做 upsert。這兩個 collection 若已有舊資料,請先確認 `_id` 的格式(`db.FinancialTimes.findOne()`),否則同一篇文章可能會以不同 `_id` 重複出現。

### 執行輸出範例

```
Found 2 .txt file(s)
  Data/FT/a.txt: 74 records
  Data/FT/b.txt: 2 records
Parsed 76 records total, 74 unique by proquest_id (2 duplicate)
MongoDB 115_Text_Project.FinancialTimes: wrote 76 records (collection now has 76 documents)
```

可以用「Found N .txt file(s)」與每個檔案的筆數確認有沒有漏檔。

## 去重與重複執行

- 以 `ProQuest 文件識別碼`(`proquest_id`)當唯一鍵,用 upsert 寫入(MongoDB 的 `_id` 也是它)。
- 同一篇文章出現在多個檔案(例如匯出日期區間重疊),或整批重跑,都會合併成一筆,不會重複。
- 重跑時內容欄位會被新資料覆蓋;`created_at` 保持第一次寫入的時間。
- 單一檔案解析失敗只會印警告並跳過,不影響其他檔案。

## 資料庫欄位

SQLite 的 `news` 表(MongoDB 文件欄位相同):

| 欄位 | 來源(txt 內的欄位) |
|---|---|
| `proquest_id` | ProQuest 文件識別碼(主鍵) |
| `publication_title` | 出版物名稱 |
| `title` | 標題 |
| `publication_date` | 出版日期 |
| `section` | 區段 |
| `url` | 文件 URL |
| `abstract` | 摘要 |
| `full_text` | 全文 |
| `author` | 作者 |
| `created_at` | 第一次寫入資料庫的時間(UTC ISO 格式,程式產生) |

舊版資料庫缺少 `section` 或 `created_at` 時,下次執行會自動補欄位,不需要刪檔重建。

## txt 檔格式與解析方式

- 每筆新聞以一行 60 個底線(`____...`)分隔;檔案最後一段(聯絡我們、條款)不是新聞,會被略過。
- 一筆新聞內,各欄位之間以空行分隔,每個欄位以 `中文欄位名: 內容` 開頭;`全文` 的多個段落之間沒有空行。
- 只有已知欄位名稱(白名單)且出現在區塊**第一行**才視為欄位,避免內文中的 `She added: ...` 這類文字被誤判。

## 專案結構

```
main.py              入口:找檔案 → 解析 → 寫入資料庫
newsdb/parser.py     ProQuest txt 解析
newsdb/db/sqlite_db.py   SQLite 寫入
newsdb/db/mongo_db.py    MongoDB 寫入
environment.yml      mamba 環境定義
```
