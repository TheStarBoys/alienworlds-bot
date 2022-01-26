from time import sleep
import time
from random import randint
import os
import pprint
import platform
import json
from argparse import ArgumentParser
import warnings
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as wait_tasks

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException

from fake_useragent import UserAgent

system = platform.system()

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Constant
MAX_WORKERS = 10

WAX_USER_NAME_INPUT_XPATH = '/html/body/div[1]/div/div/div/div[1]/div/div[4]/div/div/div/div[1]/div[1]/input'
WAX_PASSWORD_INPUT_XPATH = '/html/body/div[1]/div/div/div/div[1]/div/div[4]/div/div/div/div[1]/div[2]/input'
WAX_LOG_IN_BUTTON_XPATH = '/html/body/div[1]/div/div/div/div[1]/div/div[4]/div/div/div/div[4]/button'
WAX_LOG_IN_AUTHENTICATION = '/html/body/div[1]/div/section/div[2]/div/div[1]/span'
WAX_APPROVE_TX_BUTTON_XPATH = '/html/body/div/div/section/div[2]/div/div[5]/button'

AW_PLAY_NOW_BUTTON_XPATH = '/html/body/div/div[3]/div/div[1]/div/div/div/div/span'
AW_MINE_BUTTON_XPATH = '/html/body/div/div[3]/div[1]/div/div[3]/div[5]/div[2]/div/div/div/div/div/div'
AW_MINE_BUTTON_TEXT_XPATH = AW_MINE_BUTTON_XPATH + '/span'
AW_CLAIM_MINE_BUTTON_XPATH = '/html/body/div/div[3]/div[1]/div/div[3]/div[5]/div[2]/div/div/div/div/div'
AW_CLAIM_MINE_BUTTON_TEXT_XPATH = AW_CLAIM_MINE_BUTTON_XPATH + '/span'
AW_NEXT_MINE_ATTEMPTS_TEXT_XPATH = '/html/body/div/div[3]/div[1]/div/div[3]/div[5]/div[2]/p[2]'
AW_CHARGE_TIME_HOUR_TEXT_XPATH = '/html/body/div/div[3]/div[1]/div/div[3]/div[5]/div[2]/p[1]/span[1]'
AW_CHARGE_TIME_MIN_TEXT_XPATH = '/html/body/div/div[3]/div[1]/div/div[3]/div[5]/div[2]/p[1]/span[2]'
AW_CHARGE_TIME_SEC_TEXT_XPATH = '/html/body/div/div[3]/div[1]/div/div[3]/div[5]/div[2]/p[1]/span[3]'

AW_TLM_BALANCE_TEXT_XPATH = '/html/body/div/div[3]/div[1]/div/div[3]/div[1]/div/div[2]/p[1]'

# Global variables
conf = []
firefox_path = ""
geckodriver_path = ""
args = ""


def parse_args():
    parser = ArgumentParser()
    parser.add_argument("--headless", help="Run headless", action='store_true')
    parser.add_argument("-v", "--verbose", help="Verbose mode", action='store_true')

    return parser.parse_args()


def debug_print(data):
    if args.verbose:
        print("[DEBUG] {}: {}".format(time.ctime(time.time()), data))


def debug_print_with_user(username, data):
    if args.verbose:
        print('[DEBUG] {}: miner "{}" >>> {}'.format(time.ctime(time.time()), username, data))


def print_with_user(username, *args):
    print('[INFO] {}: miner "{}" >>> '.format(time.ctime(time.time()), username), *args)


def random_sleep(username='SYSTEM', min_sec=5, max_sec=10):
    sec = randint(min_sec, max_sec)
    debug_print_with_user(username, 'random sleep for {} seconds'.format(sec))
    sleep(sec)


def load_conf():
    print("- Loading configuration -")

    f = open('conf.json')
    data = json.load(f)
    f.close()

    print("== Initializing firefox and geckodriver ==")

    firefox_path = data["firefox_path"]

    debug_print("Current system : " + str(system))

    if firefox_path == "":
        if system == "Windows":
            data["firefox_path"] = "C:/Program Files/Mozilla Firefox/firefox.exe"
        elif system == "Linux":
            data["firefox_path"] = "/usr/bin/firefox"
        elif system == 'Darwin':
            data["firefox_path"] = '/Applications/Firefox.app/Contents/MacOS/firefox'
        else:
            print("Error, system don't match")

    if system == "Windows":
        data["geckodriver_path"] = os.path.abspath(os.getcwd()).replace('\\',
                                                                        '/') + "/bin/geckodriver/windows/geckodriver.exe"
    elif system == "Linux":
        data["geckodriver_path"] = os.path.abspath(os.getcwd()).replace('\\',
                                                                        '/') + "/bin/geckodriver/linux/geckodriver"
    elif system == 'Darwin':
        data["geckodriver_path"] = os.path.abspath(os.getcwd()).replace('\\',
                                                                        '/') + "/bin/geckodriver/darwin/geckodriver"
    else:
        print("Error, system don't match")

    return data


def check_exists_by_xpath(driver: WebDriver, xpath):
    try:
        driver.find_element_by_xpath(xpath)
    except NoSuchElementException:
        return False
    return True


def wait_for_element(driver: WebDriver, xpath, refresh_count=30, refresh_on_timeout=False, username='SYSTEM'):
    count = 0
    while not check_exists_by_xpath(driver, xpath):
        debug_print_with_user(username, "Element not found, retrying")
        sleep(1)
        count += 1
        if count >= refresh_count:
            if refresh_on_timeout:
                debug_print_with_user(username, "Element not found after " + str(count) +
                                      " tries, reloading website\n---" + str(xpath))
                driver.refresh()
            else:
                debug_print_with_user(username, "Element not found after " + str(count) +
                                      " tries, exiting\n---" + str(xpath))
                return False
    return True


def login_wax(driver: WebDriver, username: str, password: str, login_method: str) -> bool:
    print_with_user(username, "Login in")
    driver.get("https://all-access.wax.io/")

    if load_user_cookies(driver, username):
        return True
    logged_in = False
    if login_method == 'wax':
        logged_in = connect_wax(driver, username, password)
    elif login_method == 'reddit':
        logged_in = connect_wax_with_reddit(driver, username, password)

    if logged_in:
        store_user_cookies(driver, username)

    return logged_in


def connect_wax(driver: WebDriver, username: str, password: str) -> bool:
    print_with_user(username, "Connect wax")

    random_sleep(username)

    debug_print_with_user(username, 'Waiting for wax user login')
    if wait_for_element(driver, WAX_USER_NAME_INPUT_XPATH, 10, True, username=username):
        debug_print_with_user(username, 'Typing wax user name')
        random_sleep(username, min_sec=2, max_sec=5)
        driver.find_element_by_xpath(WAX_USER_NAME_INPUT_XPATH).send_keys(username)

        debug_print_with_user(username, 'Typing wax user password')
        random_sleep(username, min_sec=2, max_sec=5)
        driver.find_element_by_xpath(WAX_PASSWORD_INPUT_XPATH).send_keys(password)
        debug_print_with_user(username, 'Login wax user')
        random_sleep(username, min_sec=1, max_sec=2)
        driver.find_element_by_xpath(WAX_LOG_IN_BUTTON_XPATH).click()
        # If we get challenge, manually handle it.
        if wait_for_element(driver, WAX_LOG_IN_AUTHENTICATION, 10, False, username=username):
            print_with_user(username, 'Please resolve challenge manually within 10 minutes')
            duration = 600
            while duration > 0 and check_exists_by_xpath(driver, WAX_LOG_IN_AUTHENTICATION):
                sleep(0.1)
                duration -= 0.1
            # If time out, report failure
            if duration <= 0:
                return False
        return True
    else:
        debug_print_with_user(username, "Can't login with wax")
        return False


def connect_wax_with_reddit(driver: WebDriver, username: str, password: str) -> bool:
    print("- Login with Reddit -")
    while driver.current_url == "https://all-access.wax.io/":
        random_sleep(username)
        if wait_for_element(driver, '//*[@id="reddit-social-btn"]', 30, True, username=username):
            # Click on reddit button | https://all-access.wax.io/
            driver.find_element_by_xpath('//*[@id="reddit-social-btn"]').click()
            random_sleep(username)

    if wait_for_element(driver, '//*[@id="loginUsername"]', 5, username=username):
        driver.find_element_by_xpath('//*[@id="loginUsername"]').send_keys(username)
        driver.find_element_by_xpath('//*[@id="loginPassword"]').send_keys(password)

        driver.find_element_by_xpath('/html/body/div/main/div[1]/div/div[2]/form/fieldset[5]/button').click()

    # Click on allow button | allow wax to access to reddit
    if wait_for_element(driver, '/html/body/div[3]/div/div[2]/form/div/input[1]', username=username):
        driver.find_element_by_xpath('/html/body/div[3]/div/div[2]/form/div/input[1]').click()

    else:
        print("Error, can't find Reddit login button")
        return False


# Returns true if load success
def load_user_cookies(driver: WebDriver, username: str):
    debug_print_with_user(username, 'Trying load user cookies, current page: {}'.format(driver.current_url))
    driver.delete_all_cookies()
    try:
        file = open('data/accounts/' + username + '/wax_cookies.json', 'r')
    except Exception as e:
        print_with_user(username, 'Open cookies file error: {}'.format(e))
        return False
    for cookie in json.load(file):
        try:
            driver.add_cookie(cookie)
        except Exception as e:
            print_with_user(username, 'Load cookies error: {}'.format(e))
    file.close()
    # get again
    driver.get("https://all-access.wax.io/")
    return True


def store_user_cookies(driver: WebDriver, username: str):
    debug_print_with_user(username, 'Trying store user cookies')
    if not os.path.exists('data/accounts/' + username):
        os.makedirs('data/accounts/' + username)
    try:
        with open('data/accounts/' + username + '/wax_cookies.json', 'x') as file:
            cookies = driver.get_cookies()
            json.dump(cookies, file)
    except Exception as e:
        print_with_user('Error: {}'.format(e))


def start_alien_world(driver: WebDriver, username: str) -> bool:
    while driver.current_url != "https://wallet.wax.io/dashboard":
        sleep(1)

    print_with_user(username, "Starting AlienWorlds")
    driver.get("https://play.alienworlds.io/")
    random_sleep(username)

    # Click on play now
    if wait_for_element(driver, AW_PLAY_NOW_BUTTON_XPATH, username=username):
        driver.find_element_by_xpath(AW_PLAY_NOW_BUTTON_XPATH).click()
        random_sleep(username, min_sec=10)

        return True

    return False


def mine(driver: WebDriver, username: str):
    print_with_user(username, "Start mining")
    main_page = driver.current_window_handle

    while True:
        wait_for_next_mine(driver, username)
        debug_print_with_user(username, 'Waiting for mine button')
        if wait_for_element(driver, AW_MINE_BUTTON_TEXT_XPATH, 5, True, username=username):
            # Mine button
            if driver.find_element_by_xpath(AW_MINE_BUTTON_TEXT_XPATH).text == "Mine":
                debug_print_with_user(username, 'Click on mine button')
                driver.find_element_by_xpath(AW_MINE_BUTTON_XPATH).click()
                random_sleep(username)

        debug_print_with_user(username, 'Waiting for claim mine button')
        if (
        wait_for_element(driver, AW_CLAIM_MINE_BUTTON_TEXT_XPATH, 5, False, username=username)):
            # Claim mine button
            if driver.find_element_by_xpath(AW_CLAIM_MINE_BUTTON_TEXT_XPATH).text == "Claim Mine":
                debug_print_with_user(username, 'Click on claim mine button')
                driver.find_element_by_xpath(AW_CLAIM_MINE_BUTTON_XPATH).click()
                random_sleep(username)

                debug_print_with_user(username, 'Switch to approve transaction page')
                while len(driver.window_handles) == 1:
                    sleep(1)

                # Approve transaction
                for handle in driver.window_handles:
                    if handle != main_page:
                        confirm_page = handle

                driver.switch_to.window(confirm_page)
                random_sleep(username, min_sec=3)

                debug_print_with_user(username, 'Waiting for wax approve tx button')
                if wait_for_element(driver, WAX_APPROVE_TX_BUTTON_XPATH, 30, False, username=username):
                    debug_print_with_user(username, 'Click on wax approve tx button')
                    driver.find_element_by_xpath(WAX_APPROVE_TX_BUTTON_XPATH).click()
                    random_sleep(username)

                    driver.switch_to.window(main_page)

                    # Mine success
                    if wait_for_element(driver, AW_NEXT_MINE_ATTEMPTS_TEXT_XPATH, 10, False, username=username):
                        print_with_user(username, 'Receiving bonus...')

                        if check_exists_by_xpath(driver, AW_TLM_BALANCE_TEXT_XPATH):
                            balance = driver.find_element_by_xpath(AW_TLM_BALANCE_TEXT_XPATH).text
                            print_with_user(username, "Current balance: " + str(balance) + " Trilium")
                        wait_for_next_mine(driver, username)
                else:
                    driver.switch_to.window(main_page)
                    confirm_page.close()
                    debug_print_with_user(username, "Stuck on confirmation popup, closing popup and retrying")

        random_sleep(username)


def wait_for_next_mine(driver: WebDriver, username: str, timeout=10):
    if not wait_for_element(driver, AW_NEXT_MINE_ATTEMPTS_TEXT_XPATH, 20, username=username):
        return

    charge_time = 0
    try:
        while charge_time == 0 and timeout > 0:
            hour_str = driver.find_element_by_xpath(AW_CHARGE_TIME_HOUR_TEXT_XPATH).text
            min_str = driver.find_element_by_xpath(AW_CHARGE_TIME_MIN_TEXT_XPATH).text
            sec_str = driver.find_element_by_xpath(AW_CHARGE_TIME_SEC_TEXT_XPATH).text
            charge_time = int(hour_str) * 3600 + int(min_str) * 60 + int(sec_str)
            debug_print_with_user(username, 'hour: {}, min: {}, sec: {}, charge_time: {}'.
                                  format(hour_str, min_str, sec_str, charge_time))
            timeout -= 1
            sleep(1)
    except Exception:
        pass
    print_with_user(username, 'Waiting for the next mining. Charge time: {}'.format(charge_time))
    sleep(charge_time)
    random_sleep(username)


def run_task(driver: WebDriver, username: str, password: str, login_method: str):
    if not login_wax(driver, username, password, login_method):
        print("Error, can't log in")
        driver.close()
        exit()

    if not start_alien_world(driver, username):
        print("Error while starting Alien Worlds")
        driver.close()
        exit()

    mine(driver, username)


if __name__ == '__main__':
    args = parse_args()
    conf = load_conf()

    debug_print("firefox_binary=" + conf["firefox_path"])
    debug_print("executable_path=" + conf["geckodriver_path"])

    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix='Miner') as pool:
        all_tasks = []
        for account in conf['accounts']:
            debug_print('account info: {}'.format(account))
            username, password, login_method = account['username'], account['password'], account['login_method']

            # Initialize webdriver for each account
            profile = webdriver.FirefoxProfile()

            options = Options()
            options.headless = args.headless
            options.binary_location = conf["firefox_path"]

            driver = webdriver.Firefox(options=options, firefox_profile=profile,
                                       executable_path=conf["geckodriver_path"])
            driver.set_window_size(1280, 1280)
            debug_print('driver session {} used for account {}'.format(driver.session_id, username))

            all_tasks.append(pool.submit(run_task, driver, username, password, login_method))

        wait_tasks(all_tasks)
