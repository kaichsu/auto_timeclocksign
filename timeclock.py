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
            if start <= timestamp <= end:
                return True
    return False

        
    
def action():
    # Read config and verify
    config_path = "config.json"
    config = {}
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
    except FileNotFoundError:
        print(f"File not found: {config_path}")
        exit()
    except json.JSONDecodeError:
        print(f"Error decoding JSON from file: {config_path}")
        exit()
    required_keys = ['account', 'password', 'timeclocks', 'schedule']
    for key in required_keys:
        if key not in config:
            print(f"Error: Missing required key '{key}' in config.json")
            exit()

    # Open browser and login
    chrome_options = webdriver.ChromeOptions()
    # 如果想要看到瀏覽器操作，請註解掉下面三行
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=chrome_options)
    driver.get('https://portal.nycu.edu.tw/')
    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, 'account')))
    driver.find_element(By.NAME, 'account').send_keys(config['account'])
    driver.find_element(By.NAME, 'password').send_keys(config['password'])
    driver.find_element(By.CLASS_NAME, 'login').click()
    try:    
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, 'user-name')))
    except:
        print("登入失敗，請檢查帳號密碼是否正確")
        driver.quit()
        exit()

    # Redirect to timeclocksign page
    driver.get('https://portal.nycu.edu.tw/#/redirect/timeclocksign')
    buttons = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#ContentPlaceHolder1_GridView_attend')))

    # Parse timeclocks
    trs = driver.find_element(By.XPATH, '/html/body/form/div[3]/div/div/table/tbody/tr/td/table/tbody/tr[2]/td/div/table').find_elements(By.TAG_NAME, 'tr')
    timeclocks = []
    clocking = None
    for tr in trs:
        if "Sign" not in tr.text:
            continue
        timeclocks.append(TimeClock(tr))
        if timeclocks[-1].last_sign != -1:
            clocking = timeclocks[-1]
        # print(timeclocks[-1].to_string())

    # Get time
    now = datetime.datetime.now()
    weekday = now.isoweekday()
    timestamp = now.hour * 60 + now.minute

    # check if this time is in schedulable time
    is_schedulable = in_schedule(config['schedule'], weekday, timestamp)
    
    # Determine next action
    print(f"[LOG] 當前時間 {now.strftime('%Y-%m-%d %H:%M:%S')}")
    # If the system have signed in
    if clocking != None:    
        # check if the time is reached the hoursperday limit
        is_reached = (timestamp - clocking.last_sign >= 60 * int(config['hoursperday']))
        # signed out
        if is_schedulable == False or is_reached == True:
            if is_schedulable == False:
                print(f"[簽退]:{clocking.title} 超出 schedule 時間範圍")
            elif is_reached:
                print(f"[簽退]:{clocking.title} 已經簽滿本日時數")
            clocking.tr.find_element(By.CLASS_NAME, 'input-button').click()
            confirm = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '/html/body/form/div[3]/div/div/table/tbody/tr[2]/td/input[1]')))
            confirm.click()
        else:
            print(f"[LOG] {clocking.title} 正在簽到中，最後簽到時間 {clocking.last_sign // 60} 點 {clocking.last_sign % 60} 分")
    else:
        # 判斷當前是否已經達到本日時數
        today_total_hours = 0
        for clock in timeclocks:
            today_total_hours += clock.today_hours

        is_reached = today_total_hours >= int(config['hoursperday'])
        
        # 依據 config timeclock 順序選擇一個簽到
        if is_schedulable and is_reached == False:
            priority = list()
            for target in config['timeclocks']:
                for clock in timeclocks:
                    if clock.title == target['title']:
                        priority.append(clock)
                        break
            is_signed = False
            for clock in priority:
                if clock.remain > 0:
                    print(f"[簽到]:{clock.title}")
                    clock.tr.find_element(By.CLASS_NAME, 'input-button').click()
                    confirm = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '/html/body/form/div[3]/div/div/table/tbody/tr[2]/td/input[1]')))
                    confirm.click()
                    is_signed = True
                    break
            if is_signed == False:
                print("[LOG] 無可用簽到")
    driver.quit()


def main():
    action()
    while True:
        if datetime.datetime.now() == 0:
            action()
        time.sleep(60)
    action()

if __name__ == "__main__":
    main()