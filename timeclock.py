from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import datetime
import re
import json
import time

class TimeClock:
    def __init__(self, tr):
        # parse text here
        lines = tr.text.splitlines()
        self.tr = tr
        self.title = lines[0] 
        self.detail = lines[1]
        numbers = re.findall(r'\d+', lines[2])
        self.limit = int(numbers[0])
        self.accumulate = int(numbers[1])
        self.remain = int(numbers[2])
        self.today_hours = 0
        self.last_sign = -1
        for line in lines[3:]:
            if "本日簽到時間" not in line:
                break
            times = re.findall(r'\d+:\d+', line)
            # convert HH:MM to minutes
            for index, time in enumerate(times):
                time = time.split(":")
                times[index] = int(time[0]) * 60 + int(time[1])
            
            if len(times) == 1:
                self.last_sign = times[0]
            elif len(times) == 2:
                self.today_hours += (times[1] - times[0]) // 60

    def to_string(self):
        return f"標題: {self.title}\n" \
               f"詳細: {self.detail}\n" \
               f"限制時數: {self.limit} 小時\n" \
               f"累積時數: {self.accumulate} 小時\n" \
               f"剩餘時數: {self.remain} 小時\n" \
               f"本日簽到: {self.today_hours} 小時\n" \
               f"最後簽到: {self.last_sign} 分鐘\n"
    
def in_schedule(schedules, weekday, timestamp):
    for schedule in schedules:
        if weekday == int(schedule["weekday"]):
            start = schedule['start'].split(":")
            start = int(start[0]) * 60 + int(start[1])  
            end = schedule['end'].split(":")
            end = int(end[0]) * 60 + int(end[1])
            if start <= timestamp < end:
                return True
    return False

def LOG(message):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]：{message}")

def load_config(config_path):
    config = {}
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
    except FileNotFoundError:
        LOG(f"File not found: {config_path}")
        return None
    except json.JSONDecodeError:
        LOG(f"Error decoding JSON from file: {config_path}")
        return None
    required_keys = ['account', 'password', 'timeclocks', 'schedule']
    for key in required_keys:
        if key not in config:
            LOG(f"Error: Missing required key '{key}' in config.json")
            return None
    return config
    
def action():
    config = load_config("config.json")
    if config == None:
        return

    # Open browser and login
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=chrome_options)
    driver.get('https://portal.nycu.edu.tw/#/redirect/timeclocksign')
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, 'account')))
    except:
        LOG("Timeout: Cannot find login page")
        driver.quit()
        return 
    driver.find_element(By.NAME, 'account').send_keys(config['account'])
    driver.find_element(By.NAME, 'password').send_keys(config['password'])
    driver.find_element(By.CLASS_NAME, 'login').click()

    table_xpath = '/html/body/form/div[3]/div/div/table/tbody/tr/td/table/tbody/tr[2]/td/div/table'
    trs = None
    try:    
        trs = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, table_xpath))).find_elements(By.TAG_NAME, 'tr')
    except:
        try:
            el_message = driver.find_element(By.CLASS_NAME, "el-message__content")
            LOG(f"錯誤訊息：{el_message.text}")
        except:
            pass
        LOG("登入失敗，請確認 config.json 中的 account, password ")
        driver.quit()
        return

    # Parse timeclocks from the table of the page
    timeclocks = []
    clocking = None
    for tr in trs:
        if "Sign" not in tr.text:
            continue
        timeclocks.append(TimeClock(tr))
        if timeclocks[-1].last_sign != -1:
            clocking = timeclocks[-1]
        # print(timeclocks[-1].to_string())

    # check if this time is in schedulable time
    now = datetime.datetime.now()
    weekday = now.isoweekday()
    timestamp = now.hour * 60 + now.minute
    is_schedulable = in_schedule(config['schedule'], weekday, timestamp)
    
    # Take action based on prepared infomation
    if clocking != None:    
        # check if the time is reached the hoursperday limit
        is_reached = (timestamp - clocking.last_sign >= 60 * int(config['hoursperday']))

        if is_schedulable == False or is_reached == True:
            if is_schedulable == False:
                LOG(f"簽退「{clocking.title}」(當前時間不在設定簽到時段)")
            elif is_reached:
                LOG(f"簽退「{clocking.title}」(已經簽滿本日時數{config['hoursperday']}小時)")
            clocking.tr.find_element(By.CLASS_NAME, 'input-button').click()
            try:
                confirm = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '/html/body/form/div[3]/div/div/table/tbody/tr[2]/td/input[1]')))
                confirm.click()
            except:
                LOG("簽退失敗")
        else:
            LOG(f"正在簽到「{clocking.title}」中，本日簽到時間：{clocking.last_sign // 60}:{clocking.last_sign % 60}")
    else:
        # 判斷當前是否已經達到本日時數
        today_total_hours = 0
        for clock in timeclocks:
            today_total_hours += clock.today_hours
        is_reached = today_total_hours >= int(config['hoursperday'])
        
        # 依據 config timeclock 順序選擇一個簽到
        if is_schedulable and is_reached == False:
            priority = list()
            # 排序 priority
            for item in config['timeclocks']:
                index = int(item['index'])
                if index >= len(timeclocks):
                    LOG("config.json 中的 timeclock index 超出範圍")
                    continue
                clock = timeclocks[index]
                if clock.accumulate < int(item['hours']):
                    priority.append(clock)
                    break
            is_signed = False
            # 依據 priority 順序簽到
            for clock in priority:
                if clock.remain > 0:
                    LOG(f"簽到「{clock.title}」")
                    clock.tr.find_element(By.CLASS_NAME, 'input-button').click()
                    try:
                        confirm = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '/html/body/form/div[3]/div/div/table/tbody/tr[2]/td/input[1]')))
                        confirm.click()
                    except:
                        LOG("簽到失敗")
                    is_signed = True
                    break
            if is_signed == False:
                LOG("無可用簽到")
        else:
            message = ""
            if is_schedulable == False:
                message += "不在設定簽到時段"
            if is_reached:
                message += f"已經簽滿本日 {config['hoursperday']} 小時"
            LOG(f"{message}")
    driver.quit()


def main():
    LOG("開始執行")
    while True:
        action()
        time.sleep(1200)

if __name__ == "__main__":
    main()