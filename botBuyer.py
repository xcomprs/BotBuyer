from itertools import product
import pprint
import time
import csv
import random
import psutil
import subprocess
import smtplib
import traceback
import logging
import os
import sys
import signal
import multiprocessing
from seleniumbase import SB
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ==========================================
# 1. NOTIFICATION SERVICE
# ==========================================
class NotificationService:
    """Handles sending email notifications and error reports."""

    def __init__(self, smtp_server="smtp.gmail.com", smtp_port=587, 
                 sender_email="xxxxx@gmail.com", sender_password="xxxxxxxxxxxx", 
                 receiver_email="xxxxxxxxx"):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.receiver_email = receiver_email

    def send_email(self, message, subject="BotBuyer Email Alert!", screenshot_path=None):
        msg = MIMEMultipart()
        msg["From"] = self.sender_email
        msg["To"] = self.receiver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))

        if screenshot_path and os.path.exists(screenshot_path):
            try:
                with open(screenshot_path, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(screenshot_path)}")
                msg.attach(part)
                logging.info("Attached screenshot: %s", screenshot_path)
            except Exception as e:
                logging.error("Failed to attach screenshot: %s", e)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, self.receiver_email, msg.as_string())
            print("Email sent successfully!")
            logging.info("Email sent successfully to %s", self.receiver_email)
            time.sleep(5)
        except Exception as e:
            print(f"Failed to send email: {e}")
            logging.error("Failed to send email: %s", str(e))


# ==========================================
# 2. CSV REPOSITORY (Data Management)
# ==========================================
class CsvRepository:
    """Manages reading and writing state to the CSV database file."""

    def __init__(self, csv_file_path="./botBuyer.csv"):
        self.csv_file_path = csv_file_path

    def get_status_by_id(self, product_id):
        try:
            with open(self.csv_file_path, mode="r", newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if row.get("id") == product_id:
                        return row.get("status")
        except FileNotFoundError:
            print(f"CSV file '{self.csv_file_path}' not found.")
        except Exception as e:
            print(f"An error occurred: {e}")
        return None

    def update_status_by_id(self, target_id, new_status="completed"):
        rows = []
        updated = False

        try:
            with open(self.csv_file_path, mode="r", newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                fieldnames = reader.fieldnames
                for row in reader:
                    if row.get("id") == target_id:
                        row["status"] = new_status
                        updated = True
                    rows.append(row)

            if not updated:
                print(f"ID '{target_id}' not found in CSV file.")
                return False

            with open(self.csv_file_path, mode="w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            return True
        except Exception as e:
            logging.error("Failed to update status for ID %s: %s", target_id, e)
            return False

    def update_all_completed(self):
        rows = []
        updated = False
        try:
            with open(self.csv_file_path, mode="r", newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                fieldnames = reader.fieldnames
                for row in reader:
                    row["status"] = "completed"
                    updated = True
                    rows.append(row)

            if not updated:
                return False

            with open(self.csv_file_path, mode="w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            return True
        except Exception as e:
            logging.error("Failed to update all rows: %s", e)
            return False


# ==========================================
# 3. SYSTEM MANAGER (VPN, Processes, Error Monitoring)
# ==========================================
class SystemManager:
    """Handles OS-level interactions, VPN toggles, error tracking, and process cleanup."""

    def __init__(self, log_file="error_logs.log", vpn_connection_name="ca_vancouver", 
                 error_limit=9, error_time_window=180, cooldown_vpn_time=60, 
                 cooldown_time=90, notification_service=None):
        self.log_file = log_file
        self.vpn_connection_name = vpn_connection_name
        self.error_limit = error_limit
        self.error_time_window = error_time_window
        self.cooldown_vpn_time = cooldown_vpn_time
        self.cooldown_time = cooldown_time
        self.notifier = notification_service
        self._setup_logging()

    def _setup_log_rotation(self):
        if os.path.exists(self.log_file):
            try:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                new_log_file = f"error_logs_{timestamp}.log"
                os.rename(self.log_file, new_log_file)
                print(f"✅ Renamed existing log file '{self.log_file}' to '{new_log_file}'")
            except PermissionError:
                print("❌ PermissionError: The log file is being used by another process.")

    def _setup_logging(self):
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        self._setup_log_rotation()
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def turn_off_vpn(self):
        try:
            subprocess.run(["nmcli", "con", "down", self.vpn_connection_name], check=True, capture_output=True, text=True)
            print("VPN turned off.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to turn off VPN: {e.stderr}")
            logging.error("Failed to turn off VPN: %s", str(e))

    def turn_on_vpn(self):
        try:
            subprocess.run(["nmcli", "con", "up", self.vpn_connection_name], check=True, capture_output=True, text=True)
            print("VPN turned on.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to turn on VPN: {e.stderr}")
            logging.error("Failed to turn on VPN: %s", str(e))

    def cooldown_with_vpn_toggle(self, cooldown_time=300):
        print("Initiating cooldown procedure with VPN toggle.")
        logging.info("Turning Off the VPN.")
        self.turn_off_vpn()
        print(f"Cooldown: Waiting for {cooldown_time} seconds...")
        time.sleep(cooldown_time)
        logging.info("Turning ON the VPN.")
        self.turn_on_vpn()
        print("Cooldown complete; VPN connection restored.")

    def get_last_error_timestamps(self):
        if not os.path.exists(self.log_file):
            return []
        
        timestamps = []
        current_time = time.time()
        try:
            with open(self.log_file, "r") as f:
                lines = f.readlines()
            for line in reversed(lines):
                if "ERROR" in line:
                    timestamp_str = line.split(" - ")[0]
                    log_time = time.mktime(time.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S"))
                    if current_time - log_time <= self.error_time_window:
                        timestamps.append(log_time)
                    else:
                        break
        except Exception as e:
            logging.error("Failed to read log file: %s", str(e))
        return timestamps

    def check_error_rate(self):
        error_timestamps = self.get_last_error_timestamps()
        if len(error_timestamps) >= self.error_limit:
            logging.warning("Too many errors! Pausing execution for 5 minutes.")
            if self.notifier:
                self.notifier.send_email("Too many errors! Pausing execution for 5 minutes.", "System Paused")
            self.cooldown_with_vpn_toggle(self.cooldown_vpn_time)
            time.sleep(self.cooldown_time)
            logging.info("Resuming execution after cooldown.")

    def kill_browser_process(self, process_pid):
        try:
            parent = psutil.Process(process_pid)
        except psutil.NoSuchProcess:
            logging.info(f"Parent process with PID {process_pid} not found.")
            return

        time.sleep(3)
        try:
            children = parent.children(recursive=True)
        except psutil.Error as e:
            logging.error(f"Error retrieving children of PID {process_pid}: {e}")
            children = []

        chrome_keywords = ["chrome", "chromedriver", "google-chrome"]
        for child in children:
            try:
                child_name = child.name().lower()
                if any(keyword in child_name for keyword in chrome_keywords):
                    logging.info(f"Terminating child process: {child.name()} (PID: {child.pid})")
                    print(f"Terminating child process: {child.name()} (PID: {child.pid})")
                    child.terminate()
            except psutil.NoSuchProcess:
                continue
            except Exception as e:
                logging.error(f"Error terminating child process (PID: {child.pid}): {e}")

        gone, alive = psutil.wait_procs(children, timeout=10)
        if alive:
            for child in alive:
                try:
                    logging.info(f"Force killing child process: {child.name()} (PID: {child.pid})")
                    print(f"Force killing child process: {child.name()} (PID: {child.pid})")
                    child.kill()
                except Exception as e:
                    logging.error(f"Error force killing child process (PID: {child.pid}): {e}")

        try:
            logging.info(f"Terminating parent process (PID: {process_pid})")
            parent.terminate()
            try:
                parent.wait(5)
            except psutil.TimeoutExpired:
                logging.info(f"Force killing parent process (PID: {process_pid}) after timeout.")
                parent.kill()
        except psutil.NoSuchProcess:
            logging.info(f"Parent process with PID {process_pid} no longer exists at termination time.")
        except Exception as e:
            logging.error(f"Error terminating parent process (PID: {process_pid}): {e}")


# ==========================================
# 4. BOT WORKER (Web Automation Task)
# ==========================================
class BotWorker:
    """Executes the specific SeleniumBase purchasing/alert workflows."""

    def __init__(self, url, row_id, notification_service, csv_repository, system_manager):
        self.url = url
        self.row_id = row_id
        self.notifier = notification_service
        self.csv_repo = csv_repository
        self.sys_manager = system_manager

    def run_main(self):
        productId = self.row_id
        print(f"Process PID: {os.getpid()} is opening URL: {self.url}")
        
        with SB(uc=True, test=True, locale_code="en", ad_block=True) as driver:
            try:
                driver.activate_cdp_mode(self.url)
                title = driver.get_page_title()
                print(f"Title: {title} - Process ID: {os.getpid()} - Product Id: {productId}")

                status = self.csv_repo.get_status_by_id(productId)
                foundButton = False
                goToCart = False
                contCheckout = False
                guestContinue = False
                addressInput = False
                contPayment = False
                cardNumberPayment = False
                clickConhtinue = False
                clickOrderNow = False

                if status != "completed":
                    while not foundButton:
                        driver.sleep(5)
                        if driver.is_element_visible(".onetrust-close-btn-handler"):
                            driver.wait_for_element_clickable(".onetrust-close-btn-handler", timeout=10)
                            driver.click(".onetrust-close-btn-handler")                    
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            print("Cookie banner closed!")
                        else:
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            print("Cookie banner close button not found.")
                            logging.info("Cookie banner close button not found.")

                        if driver.is_element_visible("#delivery"):
                            driver.wait_for_element_clickable("#delivery", timeout=10)
                            driver.click("#delivery")
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("Clicked the Delivery button.")
                            logging.info("Clicked the Delivery button.")
                        else:
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("Delivery button is not visible.")
                            raise Exception('Error Delivery button is not visible.')        
    
                        driver.sleep(2.5)    
                    
                        if driver.is_element_enabled('[data-automation="addToCartButton"]'):   
                            driver.click('[data-automation="addToCartButton"]')
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint('addToCartButton button is enabled')
                            self.notifier.send_email(f"Title: {title} Added to Cart - Urgent !!!! Product URL: {self.url}")
                            driver.sleep(5)
                            foundButton = True
                            logging.info('addToCartButton button is enabled')                        
                        else:
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint('addToCartButton is not enabled')
                            logging.info('addToCartButton is not enabled')               
                            driver.sleep(random.uniform(5, 10))
                            pprint.pprint('Refreshing')                                                                                                       
                            driver.refresh()

                    driver.sleep(2.5)
                    countGoToCart = 0
                    while not goToCart:
                        if driver.is_element_visible('[data-automation="go-to-cart"]'):
                            driver.wait_for_element_clickable('[data-automation="go-to-cart"]', timeout=10)
                            driver.click('[data-automation="go-to-cart"]')
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("go-to-cart")
                            logging.info("go-to-cart")
                            goToCart = True
                        else:
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("error is not go-to-cart.")
                            logging.info("error is not go-to-cart.")   
                            driver.save_screenshot("error.png")                            
                            driver.sleep(10)
                            countGoToCart += 1
                            if countGoToCart >= 6:
                                self.notifier.send_email("Error go-to-cart", "Error go-to-cart", "error.png")                       
                                logging.info("Error go-to-cart")                          
                                parent = psutil.Process(os.getpid())
                                parent.wait()    
    
                    driver.sleep(10)
                    countCheckout = 0
                    while not contCheckout:
                        if driver.is_element_visible("[data-automation='continue-to-checkout']"):
                            driver.wait_for_element_clickable("[data-automation='continue-to-checkout']", timeout=10)
                            driver.click("[data-automation='continue-to-checkout']")
                            driver.sleep(2.5)
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("click Checkout")
                            logging.info("click Checkout")
                            contCheckout = True
                        else:
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("error click Checkout")
                            driver.save_screenshot("error.png")
                            driver.sleep(10)
                            countCheckout += 1
                            if countCheckout >= 6:
                                self.notifier.send_email("Error Checkout", "Error Checkout", "error.png")                                
                                logging.info("Error Checkout")                          
                                parent = psutil.Process(os.getpid())
                                parent.wait()                            

                    driver.sleep(5)
                    countGuestContinue = 0
                    while not guestContinue:
                        if driver.is_element_visible("[data-automation='guest-continue']"):
                            driver.wait_for_element_clickable("[data-automation='guest-continue']", timeout=10)
                            driver.click("[data-automation='guest-continue']")
                            driver.sleep(2.5)
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("click guest-continue")
                            logging.info("click guest-continue")
                            guestContinue = True
                        else:
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("error click guest-continue")
                            driver.save_screenshot("error.png")
                            driver.sleep(10)
                            countGuestContinue += 1
                            if countGuestContinue >= 6: 
                                self.notifier.send_email("Error guest-continue", "Error guest-continue", "error.png")                               
                                logging.info("Error guest-continue")                          
                                parent = psutil.Process(os.getpid())
                                parent.wait()  
    
                    driver.sleep(5)
                    countAddressInput = 0
                    while not addressInput:
                        if driver.is_element_visible('[data-automation="addressInput"]'):   
                            driver.type("#email", "xxxxxx@xxxxx.com")
                            driver.type('[data-automation="firstNameInput"]', "First name")
                            driver.type('[data-automation="lastNameInput"]', "last name")
                            driver.type('[data-automation="phoneInput"]', "xxx-xxx-xxxx")    

                            street = driver.find_element('[data-automation="addressInput"]')
                            for i in "xx-xxxxx street xx":
                                street.send_keys(i)
                                time.sleep(random.uniform(0, 0.5))
                            auto = driver.find_element('[data-automation="addressInput"]')
                            time.sleep(random.uniform(0, 5))
                            auto.send_keys(Keys.ENTER)
                            time.sleep(random.uniform(0, 5))

                            driver.type('[data-automation="addressInput"]', "xx-xxxxx street xxx")
                            driver.type('[data-automation="cityInput"]', "Langley")
                            driver.type('[data-automation="postalCodeInput"]', "V2Y 3K8")
                    
                            driver.scroll_to("#regionCode")
                            driver.wait_for_element_visible("#regionCode", timeout=5)
                            driver.select_option_by_value("#regionCode", "BC")

                            pprint.pprint("Address form filled successfully!")
                            addressInput = True
                        else:
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("error addressInput is not Available")
                            driver.save_screenshot("error.png")
                            driver.sleep(10)
                            countAddressInput += 1
                            if countAddressInput >= 6:
                                self.notifier.send_email("Error addressInput is not Available", "Error addressInput is not Available", "error.png")                                
                                logging.info("Error addressInput is not Available")                          
                                parent = psutil.Process(os.getpid())
                                parent.wait() 
    
                    driver.sleep(5)
                    countPayment = 0
                    while not contPayment:                        
                        if driver.is_element_visible("[data-automation='continue-to-payment']"):
                            driver.wait_for_element_clickable("[data-automation='continue-to-payment']", timeout=10)
                            driver.click("[data-automation='continue-to-payment']")
                            driver.sleep(2.5)
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("click continue-to-payment")
                            logging.info("click continue-to-payment")
                            contPayment = True
                        else:
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("error click Continue")
                            driver.save_screenshot("error.png")
                            driver.sleep(10)                        
                            countPayment += 1
                            if countPayment >= 6:
                                self.notifier.send_email("Error payment", "Error payment", "error.png")                           
                                logging.info("Error payment")                          
                                parent = psutil.Process(os.getpid())
                                parent.wait() 

                    driver.sleep(15)
                    countCardPayment = 0
                    while not cardNumberPayment:                        
                        if driver.is_element_visible("#shownCardNumber"):
                            ccard = driver.find_element("#shownCardNumber")
                            for i in "xxxx xxxx xxxx xxxx":
                                ccard.send_keys(i)
                                time.sleep(random.uniform(0, 0.5))
                            autoCard = driver.find_element("#shownCardNumber")
                            time.sleep(random.uniform(0, 5))
                            autoCard.send_keys(Keys.ENTER)
                            time.sleep(random.uniform(0, 5))

                            driver.type("#shownCardNumber", "xxxx xxxx xxxx xxxx")
                            driver.scroll_to("#expirationMonth")
                            driver.wait_for_element_visible("#expirationMonth", timeout=5)
                            driver.select_option_by_value("#expirationMonth", "x")
                            driver.scroll_to("#expirationYear")
                            driver.wait_for_element_visible("#expirationYear", timeout=5)
                            driver.select_option_by_value("#expirationYear", "xxxx")
                            driver.type("#cvv", "xxx")
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("Credit card details entered and scrolled successfully!")
                            logging.info("Credit card details entered and scrolled successfully!")
                            cardNumberPayment = True                        
                        else:
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("error shownCardNumber")
                            driver.save_screenshot("error.png")
                            driver.sleep(10)                        
                            countCardPayment += 1
                            if countCardPayment >= 6:
                                self.notifier.send_email("shownCardNumber", "shownCardNumber", "error.png")                           
                                logging.info("Error shownCardNumber")                          
                                parent = psutil.Process(os.getpid())
                                parent.wait() 

                    driver.sleep(15)
                    countClickConhtinue = 0
                    while not clickConhtinue:  
                        if driver.is_element_visible("[data-automation='review-order']"):
                            driver.wait_for_element_clickable("[data-automation='review-order']", timeout=15)
                            driver.click("[data-automation='review-order']")
                            driver.sleep(2.5)
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("clicked Continue")
                            logging.info("clicked Continue")
                            clickConhtinue = True
                        else:
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("error click Continue")
                            driver.save_screenshot("error.png")
                            driver.sleep(10)
                            countClickConhtinue += 1
                            if countClickConhtinue >= 6:
                                self.notifier.send_email("Error review-order", "Error review-order", "error.png") 
                                logging.info("Error review-order")                          
                                parent = psutil.Process(os.getpid())
                                parent.wait()                      

                    driver.sleep(15)
                    countClickOrderNow = 0
                    while not clickOrderNow:
                        if driver.is_element_visible(".order-now"):
                            driver.wait_for_element_clickable(".order-now", timeout=15)
                            driver.click(".order-now")
                            driver.sleep(2.5)
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("Order Placed successfully")
                            logging.info("Order Placed successfully")                  
                            driver.sleep(60)
                            self.notifier.send_email("Order Placed successfully")                     

                            driver.sleep(2.5)
                            driver.save_screenshot("Order.png")
                            if self.csv_repo.update_status_by_id(productId):
                                driver.sleep(2.5)
                            self.notifier.send_email("Order Placed successfully", "Order Placed successfully", "Order.png")
                            driver.sleep(30)
                            clickOrderNow = True
                            
                            parent = psutil.Process(os.getpid())
                            parent.wait()                        
                            pprint.pprint("allDone")
                            self.notifier.send_email("allDone")
                            logging.info("allDone")                        
                        else:
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint("error Order Placed")
                            driver.save_screenshot("error.png")
                            self.notifier.send_email("Error click Continue", "Error click Continue", "error.png")
                            driver.sleep(5)
                            countClickOrderNow += 1
                            if countClickOrderNow >= 6:                           
                                raise Exception('error Order Placed')                             
                else: 
                    print(f"Title: {title} - Process ID: {os.getpid()} is Done. Nothing to Do!")

            except Exception as e:
                print(f"Title: {title} - Process ID: {os.getpid()}")
                print(f"Error occurred: {e}")            
                logging.error("Error: %s", str(e))     
                self.sys_manager.check_error_rate()
                if str(e) != 'Error Delivery button is not visible.':
                    self.notifier.send_email(str(e))
                    time.sleep(2.5)

                try:
                    self.sys_manager.kill_browser_process(os.getpid())
                    time.sleep(3)
                except Exception as ex:
                    print("Could not obtain or kill the browser process:", ex)                   
                logging.error(f"Title: {title} Failed: %s", str(e))

            finally:         
                print(f"Title: {title} - Process ID: {os.getpid()}")
                print("Process Finished")
                logging.info("Process Finished")            

    def run_main_alert(self):
        productId = self.row_id
        print(f"Process PID: {os.getpid()} is opening URL: {self.url}")
        
        with SB(uc=True, test=True, locale_code="en", ad_block=True) as driver:
            try:
                driver.activate_cdp_mode(self.url)
                title = driver.get_page_title()
                print(f"Title: {title} - Process ID: {os.getpid()} - Product Id: {productId}")

                status = self.csv_repo.get_status_by_id(productId)
                foundButton = False
                foundStore = False

                if status != "completed":
                    while not foundButton:
                        driver.sleep(5)
                        get_it_new_xpath = "//a[contains(@class, 'c-000 column align-items-center')]//span[contains(text(), 'Get it NEW')]"
                        driver.sleep(2.5)
                        if driver.is_element_visible(get_it_new_xpath, by="xpath"):
                            print("✅ Clicking on 'Get it NEW'")
                            driver.click(get_it_new_xpath, by="xpath")
                        else:
                            print("❌ 'Get it NEW' element not found or not visible")
                            logging.info("❌ 'Get it NEW' element not found or not visible")     
                
                        if driver.is_element_enabled('[data-button-action="add-to-cart"]'): 
                            driver.click('[data-button-action="add-to-cart"]')
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint('addToCartButton button is enabled')
                            self.notifier.send_email(f"Title: {title} Added to Cart - Urgent !!!! Product URL: {self.url}")
                            driver.sleep(5)
                            foundButton = True
                            logging.info('addToCartButton button is enabled')
                            parent = psutil.Process(os.getpid())
                            parent.wait()

                        if driver.is_element_visible("//span[contains(text(), 'Check Other Stores')]", by="xpath"):
                            driver.sleep(2.0)
                            driver.click("//span[contains(text(), 'Check Other Stores')]", by="xpath")
                            driver.sleep(3)

                            if driver.is_element_visible('button[data-target="#collapseBC"]'):
                                driver.sleep(3)
                                driver.click('button[data-target="#collapseBC"]')
                                cities = ["Coquitlam", "Surrey", "Burnaby", "Richmond"]

                                for city in cities:
                                    try:
                                        stock_xpath = f"//span[contains(text(),'{city}')]/following-sibling::span"
                                        if driver.is_element_visible(stock_xpath):
                                            stock = int(driver.get_text(stock_xpath).strip())
                                            if stock > 0:
                                                print(f"{city} has stock: {stock}. Clicking 'Set Preferred Store'.")
                                                button_xpath = f"//span[contains(text(),'{city}')]/following::div[contains(text(),'Set Preferred Store')][1]"                                            
                                                if driver.is_element_visible(button_xpath):
                                                    driver.sleep(3)
                                                    driver.scroll_to(button_xpath)
                                                    driver.click(button_xpath)
                                                    driver.sleep(2)
                                                    foundStore = True
                                                    break
                                                else:
                                                    print(f"'Set Preferred Store' button not found for {city}")
                                            else:
                                                print(f"{city} is out of stock. Skipping.")
                                        else:
                                            print(f"Stock information not found for {city}. Skipping.")
                                    except Exception as e:
                                        print(f"Error processing {city}: {e}")

                                if foundStore:
                                    if driver.is_element_enabled('[data-button-action="add-to-cart"]'): 
                                        driver.click('[data-button-action="add-to-cart"]')
                                        print(f"Title: {title} - Process ID: {os.getpid()}")
                                        pprint.pprint('addToCartButton button is enabled')
                                        self.notifier.send_email(f"Title: {title} Added to Cart - Urgent !!!! Product URL: {self.url}")
                                        driver.sleep(5)
                                        foundButton = True
                                        logging.info('addToCartButton button is enabled')
                                        parent = psutil.Process(os.getpid())
                                        parent.wait()  

                        if driver.is_element_visible("//div[@class='open-box-status']/ancestor::a"): 
                            driver.click("//div[@class='open-box-status']/ancestor::a")                            
                            pprint.pprint("Has Open Box")

                            if driver.is_element_enabled('[data-button-action="add-to-cart"]'):
                                driver.click('[data-button-action="add-to-cart"]')
                                print(f"Title: {title} - Process ID: {os.getpid()}")
                                pprint.pprint('addToCartButton button is enabled')
                                self.notifier.send_email(f"Title: {title} Added to Cart - Urgent !!!! Product URL: {self.url}")
                                driver.sleep(5)
                                logging.info('addToCartButton button is enabled')
                                parent = psutil.Process(os.getpid())
                                parent.wait()
                        else:
                            print(f"Title: {title} - Process ID: {os.getpid()}")
                            pprint.pprint('addToCartButton is not enabled')
                            logging.info('addToCartButton is not enabled')               
                            driver.sleep(random.uniform(5, 10))
                            pprint.pprint('Refreshing')                                                                                                       
                            driver.refresh()           
                else: 
                    print(f"Title: {title} - Process ID: {os.getpid()} is Done. Nothing to Do!")

            except Exception as e:
                print(f"Title: {title} - Process ID: {os.getpid()}")
                print(f"Error occurred: {e}")            
                logging.error("Error: %s", str(e))     
                self.sys_manager.check_error_rate()
                if str(e) != 'Error Delivery button is not visible.':
                    self.notifier.send_email(str(e))
                    time.sleep(2.5)

                try:
                    self.sys_manager.kill_browser_process(os.getpid())
                    time.sleep(3)
                except Exception as ex:
                    print("Could not obtain or kill the browser process:", ex)                   
                logging.error(f"Title: {title} Failed: %s", str(e))

            finally:         
                print(f"Title: {title} - Process ID: {os.getpid()}")
                print("Process Finished")
                logging.info("Process Finished")     


# ==========================================
# 5. BOT MANAGER (Orchestrator)
# ==========================================
class BotManager:
    """Manages multi-processing execution and launching tasks based on CSV configuration."""

    def __init__(self, csv_file_path="./botBuyer.csv"):
        self.csv_file_path = csv_file_path
        self.notifier = NotificationService()
        self.csv_repo = CsvRepository(csv_file_path)
        self.sys_manager = SystemManager(notification_service=self.notifier)

    def _start_process_worker(self, url, row_id):
        attempt = 0
        while True:
            attempt += 1
            print(f"[Attempt {attempt}] Starting process for ID: {row_id} - Parent Process ID: {os.getpid()}")

            if "www.canadacomputers.com" in url:
                worker = BotWorker(url, row_id, self.notifier, self.csv_repo, self.sys_manager)
                process = multiprocessing.Process(target=worker.run_main_alert)
            else:
                worker = BotWorker(url, row_id, self.notifier, self.csv_repo, self.sys_manager)
                process = multiprocessing.Process(target=worker.run_main)

            process.start()        
            process.join()
            
            time.sleep(random.uniform(2, 3))
            logging.info(f"[Attempt {attempt}] Process for URL: {url} and ID: {row_id} ended with exit code {process.exitcode}")
            
            if process.exitcode == 0:
                print(f"Process for ID {row_id} finished successfully.")
                self.notifier.send_email(f"Process for URL {url} finished successfully on attempt {attempt}.")
                break
            else:
                print(f"Process for ID {row_id} failed with exit code {process.exitcode}. Restarting in 5-8 seconds...")
                logging.info(f"Process for ID {row_id} failed with exit code {process.exitcode}. Restarting in 5-8 seconds...")
                time.sleep(random.uniform(5, 8))

    def run(self):
        if "--headed" not in sys.argv:
            sys.argv.append("--headed")

        processes = []
        
        try:
            with open(self.csv_file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if row.get("status", "").strip().lower() == "uncompleted":
                        url = row.get("url")
                        row_id = row.get("id")
                        if url and row_id:
                            p = multiprocessing.Process(target=self._start_process_worker, args=(url, row_id))
                            p.start()
                            time.sleep(random.uniform(5, 8))                    
                            processes.append((p, row_id, url))
                            print(f"Started process for ID: {row_id} and URL: {url}")
            
            for p, row_id, url in processes:
                p.join()
        except FileNotFoundError:
            print(f"Main CSV file not found at {self.csv_file_path}")
            logging.error(f"Main CSV file not found at {self.csv_file_path}")


# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    manager = BotManager()
    manager.run()
