# BotBuyer 🤖🛒

**BotBuyer** is an automated checkout and store inventory monitoring system built in Python using `SeleniumBase` (UC Mode) and `multiprocessing`. It monitors e-commerce products (such as Best Buy and Canada Computers), detects stock availability, automates cart additions, handles guest checkouts, and sends email alerts. 

This application was created in response to the scarcity of computer components—such as SSDs, RAM, and GPUs. It was the only way I could find to bypass scalpers whenever a new product is released, while also serving as a great way to study Python! It also demonstrates to recruiters and hiring managers that I still possess programming skills, even though I currently work with MuleSoft and Salesforce.
P.S. I did not use "vibe coding" (AI-generated code without full understanding).
---

## 📋 Table of Contents
1. [Key Features](#-key-features)
2. [Project Architecture](#-project-architecture)
3. [Prerequisites & Dependencies](#-prerequisites--dependencies)
4. [Installation & Configuration](#-installation--configuration)
5. [CSV Configuration](#-csv-configuration)
6. [Usage Guide](#-usage-guide)
7. [System Recovery & Error Management](#-system-recovery--error-management)
8. [Class Reference Manual](#-class-reference-manual)

---

## ✨ Key Features

- **Multi-Process Architecture:** Executes concurrent browser instances per item using Python's `multiprocessing`.
- **Anti-Bot Evasion:** Uses `SeleniumBase` CDP mode and Undetected-ChromeDriver options to bypass modern anti-bot systems.
- **Automated Purchasing Workflow (Best Buy):** Automates cookie handling, delivery selection, cart addition, checkout, address typing, credit card entry, and order submission.
- **Store-Stock Alerting (Canada Computers):** Monitors specific store locations (e.g., Coquitlam, Surrey, Burnaby, Richmond) for availability or Open Box stock.
- **Network & VPN Controls:** Automatically rotates or resets local VPN (`nmcli`) connections if error thresholds are exceeded.
- **Email Notifications:** Delivers real-time email alerts with optional error screenshots.
- **Process Management:** Integrates `psutil` to gracefully or forcefully kill hanging Chrome or ChromeDriver processes.

---

## 🏗️ Project Architecture

The application is refactored following Object-Oriented Programming (OOP) and Single Responsibility Principles (SRP):

```
botBuyer/
│
├── botBuyer.py           # Main Python application entrypoint
├── botBuyer.csv          # Task & product database
├── error_logs.log        # Active error log file
└── README.md             # Project documentation & user manual
```

### Core Classes & Responsibilities
- **`NotificationService`**: Sends email updates and handles image attachments.
- **`CsvRepository`**: Manages reading and updating task statuses in `botBuyer.csv`.
- **`SystemManager`**: Handles VPN resets, process termination (`psutil`), and error-rate monitoring.
- **`BotWorker`**: Runs web interactions for checkout (`run_main`) or stock monitoring (`run_main_alert`).
- **`BotManager`**: Orchestrates child processes and controls overall lifecycle.

---

## ⚙️ Prerequisites & Dependencies

### Prerequisites
- **Operating System:** Linux (Ubuntu/Debian recommended for `nmcli` VPN controls) or Windows.
- **Python:** Python 3.9+
- **Browser:** Google Chrome installed.

### Dependencies
Install the required packages using `pip`:

```bash
pip install seleniumbase psutil
```

*(Standard library packages used: `multiprocessing`, `smtplib`, `logging`, `csv`, `subprocess`, `email`, `time`, `random`, `os`, `sys`).*

---

## 📥 Installation & Configuration

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/your-username/botBuyer.git
   cd botBuyer
   ```

2. **Configure Email Credentials:**
   Open `botBuyer.py` and set your SMTP settings inside `BotManager` or directly in `NotificationService`:
   ```python
   self.notifier = NotificationService(
       smtp_server="smtp.gmail.com",
       smtp_port=587,
       sender_email="your_email@gmail.com",
       sender_password="your_app_password",
       receiver_email="target_email@gmail.com"
   )
   ```

3. **Configure VPN Name (Optional):**
   If using Linux NetworkManager for VPN toggling, ensure `nmcli` is configured with your profile name in `SystemManager`:
   ```python
   self.vpn_connection_name = "ca_vancouver"
   ```

---

## 📑 CSV Configuration (`botBuyer.csv`)

The bot reads tasks directly from `botBuyer.csv`. Format the file with the following headers:

```csv
id,url,status
1,https://www.bestbuy.ca/en-ca/product/example-item/123456,uncompleted
2,https://www.canadacomputers.com/product_info.php?cPath=xxx&item_id=654321,uncompleted
```

| Header | Description | Allowed Values |
| :--- | :--- | :--- |
| `id` | Unique task identifier | String / Number |
| `url` | Full product web link | URL |
| `status` | Current task status | `uncompleted`, `completed` |

---

## 🚀 Usage Guide

To run the application:

```bash
python botBuyer.py
```

### Execution Flow
1. **Startup:** `BotManager` loads `botBuyer.csv`.
2. **Filtering:** Filters rows where `status == "uncompleted"`.
3. **Process Spawning:** Spawns an isolated `multiprocessing.Process` for each item.
4. **URL Detection:**
   - **Canada Computers URLs:** Routes to `run_main_alert()` for store stock checks.
   - **All Other URLs (e.g., Best Buy):** Routes to `run_main()` for automated checkout.
5. **Completion:** Upon successful purchase, updates status to `completed` in `botBuyer.csv` and terminates.

---

## 🛡️ System Recovery & Error Management

- **Error Rate Monitoring:** Tracks error timestamps within a 3-minute window (`ERROR_TIME_WINDOW = 180`).
- **Cooldown & VPN Reset:** If 9 errors occur within 3 minutes, the system initiates a cooldown, disconnects the VPN, waits, reconnects the VPN, and resumes.
- **Process Cleanup:** If a worker process fails, `psutil` cleans up hanging Chrome processes by PID before restarting the worker thread.
- **Log Rotation:** Renames existing log files on startup (`error_logs_YYYYMMDD_HHMMSS.log`) to keep logs clean.

---

## 📘 Class Reference Manual

### 1. `NotificationService`
Constructs and sends MIME multipart email alerts. Supports plain text bodies and image attachments (e.g., error/confirmation screenshots).

### 2. `CsvRepository`
Implements simple database-like operations over `botBuyer.csv`:
- `get_status_by_id(product_id)`: Fetches current status.
- `update_status_by_id(target_id, new_status)`: Thread-safe CSV updates.
- `update_all_completed()`: Batch updates all rows.

### 3. `SystemManager`
Handles system interaction:
- `turn_on_vpn()` / `turn_off_vpn()`: Calls system `nmcli` commands.
- `check_error_rate()`: Triggers cooldown if error rate exceeds `error_limit`.
- `kill_browser_process(process_pid)`: Gracefully terminates or force-kills target child browser processes.

### 4. `BotWorker`
Encapsulates browser automation logic via `SeleniumBase`:
- `run_main()`: Automates complete checkout flow.
- `run_main_alert()`: Scrapes store availability across targeted locations (e.g., British Columbia region).

### 5. `BotManager`
The orchestrator:
- Parses `botBuyer.csv`.
- Dispatches worker tasks via `multiprocessing.Process`.
- Handles automatic retry delays upon worker process failure.
