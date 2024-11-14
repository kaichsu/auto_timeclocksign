# auto_timeclocksign
依據 `config.json` 設定排程的時間自動到網頁上簽到簽退

另外，請自行閱讀程式評估要不要使用，開發者不負使用責任

## 環境設定
安裝 `python` 並且裝上 `selenium` library

## 使用方法
1. 設定 `config.json` 檔案
2. 在本工作目錄執行 `python3 timeclock.py` or `python timeclock.py`

或是使用 `run.sh` 在背景執行，可關掉終端機，並使用 `ps aux | grep timeclock` 以及 `cat timeclock.log` 確認狀態

## `config.json` 設定說明
- `account`, `password` 輸入登入的帳號
- `hoursperday` 設定每天能簽到的時數上線
- `timeclocks` 要簽到的工作
  - 這個列表的先後代表優先度，工具會先簽到列表前面的工作
  - `index` 代表該工作在簽到頁面上的順序
    - 如果要確認工具抓出來的順序，可以把 `timeclocks` 的列表內容用`to_string()`印出來
  - `hours` 代表要簽到到多少時數
- `schedule` 可以簽到的時間段
  - `weekday` 1~7 代表星期一到星期日
  - `start`, `end` 時間段的開始到結束，注意格式為 `HH:MM`
  - 另外注意現在工具無法判斷每週簽到時數，所以不要讓每週可簽到的時段超出上限