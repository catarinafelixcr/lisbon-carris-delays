# collects bus positions from the carris metropolitana api
# every 10 seconds it asks where all the buses are
# it only keeps the positions it has not seen yet
# it also saves a copy of the timetables once a week
# and the trips run per line once a day
# run it using python
# stop it with keyboard interrupt and it saves before closing
#
# built to lose as little as possible:
# - saves to disk every minute, so a crash or power cut loses 1 minute at most
# - files are written with a temporary name first, so a half written file never counts
# - file names include the timezone, so the hour that repeats when clocks go back
#   in october doesn't overwrite anything
# - any error is written down and the loop keeps going
# - the timetable download runs on the side, so the bus positions don't stop
# - on windows, it stops the pc from going to sleep while it runs
# - everything it prints also goes to data/raw/collector.log

import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

API_URL = "https://api.carrismetropolitana.pt/v2"
LISBON_TIMEZONE = ZoneInfo("Europe/Lisbon")

POLL_INTERVAL = 10           # seconds between calls
SAVE_INTERVAL = 60           # seconds between saves (1 min)
DAILY_CHECK_INTERVAL = 3600  # seconds between checks for gtfs / trips run (1 hour)

BASE_DATA_DIR = Path(__file__).resolve().parent / "data" / "raw"
VEHICLES_DIR = BASE_DATA_DIR / "vehicles"
GTFS_DIR = BASE_DATA_DIR / "gtfs"
SERVICE_DIR = BASE_DATA_DIR / "service"
POLL_LOG_FILE = BASE_DATA_DIR / "poll_log.csv"
MESSAGES_FILE = BASE_DATA_DIR / "collector.log"

NUMERIC_COLUMNS = [
    "lat", "lon", "bearing",
    "speed", "timestamp", "direction_id",
    "capacity_seated", "capacity_standing", "capacity_total"
]

api_session = requests.Session()
api_session.headers["User-Agent"] = "lisbon-carris-delays"

# gets the current time in the lisbon timezone
def get_current_time():
    return datetime.now(LISBON_TIMEZONE)

# prints a message and also writes it to a file, so i can see what happened while i was away
def log_message(text):
    line = f"{get_current_time():%Y-%m-%d %H:%M:%S} {text}"
    print(line)
    try:
        MESSAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MESSAGES_FILE, "a", encoding="utf-8") as file_handle:
            file_handle.write(line + "\n")
    except Exception:
        pass  # never stop collecting because of a message

# on windows, tells the system not to sleep while the script is running
def keep_pc_awake():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        log_message("pc won't go to sleep while this runs")
    except Exception as error_message:
        log_message(f"couldn't stop the pc from sleeping: {error_message}")

# fetches the latest vehicle positions from the api
def fetch_vehicles():
    response = api_session.get(f"{API_URL}/vehicles", timeout=15)
    response.raise_for_status()
    return pd.DataFrame(response.json())

# converts specific columns to numeric types
def fix_dataframe_types(dataframe):
    for column in dataframe.columns:
        if column in NUMERIC_COLUMNS:
            dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")
        elif column != "collected_at":
            dataframe[column] = dataframe[column].astype("string")
            
    return dataframe

# filters out vehicle positions we have already seen
def keep_only_new_positions(dataframe, seen_positions):
    vehicle_ids = dataframe["id"]
    timestamps = dataframe["timestamp"]
    position_keys = list(zip(vehicle_ids, timestamps))
    
    is_new_position_list = []
    
    for key in position_keys:
        is_new = key not in seen_positions
        is_new_position_list.append(is_new)
        seen_positions.setdefault(key, time.time())
        
    return dataframe[is_new_position_list]

# removes old positions from memory to prevent memory issues
def forget_old_positions(seen_positions, older_than=3600):
    time_limit = time.time() - older_than
    keys_to_remove = []
    
    for key, saved_timestamp in seen_positions.items():
        if saved_timestamp < time_limit:
            keys_to_remove.append(key)
            
    for key in keys_to_remove:
        del seen_positions[key]

# saves the accumulated vehicle positions to a parquet file
def save_positions_to_disk(position_buffer):
    if not position_buffer:
        log_message("nothing new to save")
        return
        
    combined_dataframe = pd.concat(position_buffer, ignore_index=True)
    fixed_dataframe = fix_dataframe_types(combined_dataframe)
    
    current_time = get_current_time()
    date_string = current_time.strftime("%Y-%m-%d")
    time_string = current_time.strftime("%H%M%S_%z")  # %z adds +0100 or +0000, so names never repeat
    
    save_folder = VEHICLES_DIR / date_string
    save_folder.mkdir(parents=True, exist_ok=True)
    
    # write with a temporary name, then rename. read_parquet ignores .part files,
    # so a file that is half written is never read
    file_path = save_folder / f"{time_string}.parquet"
    partial_path = save_folder / f"{time_string}.part"
    fixed_dataframe.to_parquet(partial_path, index=False)
    partial_path.replace(file_path)
    
    log_message(f"saved {len(fixed_dataframe)} new positions")

# logs the results of each api poll for monitoring
def log_poll_result(collected_at, total_buses, new_buses, error_message=""):
    try:
        is_first_entry = not POLL_LOG_FILE.exists()
        POLL_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        log_data = [{
            "collected_at": collected_at.isoformat(),
            "buses": total_buses,
            "new_positions": new_buses,
            "error": error_message,
        }]
        
        log_dataframe = pd.DataFrame(log_data)
        log_dataframe.to_csv(POLL_LOG_FILE, mode="a", header=is_first_entry, index=False)
    except Exception as log_error:
        # happens if the file is open in excel, for example. the positions are still saved
        print(f"couldn't write to poll log: {log_error}")

# downloads a new timetables file if the previous one is older than a week
def save_gtfs_if_outdated():
    GTFS_DIR.mkdir(parents=True, exist_ok=True)
    existing_copies = sorted(GTFS_DIR.glob("*.zip"))
    
    if existing_copies:
        last_file = existing_copies[-1]
        last_date = datetime.strptime(last_file.stem, "%Y-%m-%d").date()
        current_date = get_current_time().date()
        days_difference = (current_date - last_date).days
        
        if days_difference < 7:
            return

    current_time = get_current_time()
    date_string = current_time.strftime("%Y-%m-%d")
    final_path = GTFS_DIR / f"{date_string}.zip"
    partial_path = final_path.with_suffix(".part")  # prevents reading half downloaded files
    
    log_message("downloading gtfs...")
    # "with" closes the connection even if the download fails halfway
    with api_session.get(f"{API_URL}/gtfs", timeout=600, stream=True) as response:
        response.raise_for_status()
        
        with open(partial_path, "wb") as file_handle:
            for chunk in response.iter_content(1024 * 1024):
                file_handle.write(chunk)
            
    partial_path.replace(final_path)
    log_message(f"gtfs saved: {final_path.name}")

# saves daily trips per line if not already saved today
def save_service_metrics_if_missing():
    SERVICE_DIR.mkdir(parents=True, exist_ok=True)
    
    current_time = get_current_time()
    date_string = current_time.strftime("%Y-%m-%d")
    file_path = SERVICE_DIR / f"{date_string}.json"
    
    if file_path.exists():
        return
        
    response = api_session.get(f"{API_URL}/metrics/service/all", timeout=60)
    response.raise_for_status()
    
    partial_path = file_path.with_suffix(".part")
    partial_path.write_text(response.text, encoding="utf-8")
    partial_path.replace(file_path)
    log_message(f"trips run saved: {file_path.name}")

# executes background tasks that only need to run once per day
def execute_daily_jobs():
    try:
        save_gtfs_if_outdated()
    except Exception as error_message:
        log_message(f"save gtfs failed: {error_message}")
        
    try:
        save_service_metrics_if_missing()
    except Exception as error_message:
        log_message(f"save metrics failed: {error_message}")

# main execution loop that continuously polls the api
def run_collection_loop():
    seen_positions = {}
    position_buffer = []
    last_save_time = time.time()
    last_daily_check_time = 0
    daily_jobs_thread = None

    log_message("collecting data...")
    keep_pc_awake()
    
    try:
        while True:
            loop_start_time = time.time()

            # everything inside this try: if anything unexpected breaks,
            # it's written down and the loop carries on
            try:
                time_since_daily_check = loop_start_time - last_daily_check_time
                daily_jobs_running = daily_jobs_thread is not None and daily_jobs_thread.is_alive()

                if time_since_daily_check >= DAILY_CHECK_INTERVAL and not daily_jobs_running:
                    # runs on the side, so a slow gtfs download doesn't stop the bus positions
                    daily_jobs_thread = threading.Thread(target=execute_daily_jobs, daemon=True)
                    daily_jobs_thread.start()
                    last_daily_check_time = time.time()

                collected_time = get_current_time()
                
                try:
                    vehicles_dataframe = fetch_vehicles()
                    new_vehicles_dataframe = keep_only_new_positions(vehicles_dataframe, seen_positions)
                    
                    if len(new_vehicles_dataframe) > 0:
                        new_vehicles_dataframe = new_vehicles_dataframe.assign(collected_at=collected_time)
                        position_buffer.append(new_vehicles_dataframe)
                        
                    total_count = len(vehicles_dataframe)
                    new_count = len(new_vehicles_dataframe)
                    log_poll_result(collected_time, total_count, new_count)
                    
                except Exception as api_error:
                    log_message(f"call failed: {api_error}")
                    error_string = str(api_error)[:200]
                    log_poll_result(collected_time, 0, 0, error_message=error_string)

                time_since_last_save = time.time() - last_save_time
                
                if time_since_last_save >= SAVE_INTERVAL:
                    try:
                        save_positions_to_disk(position_buffer)
                        position_buffer = []  # only emptied if the save worked
                    except Exception as save_error:
                        log_message(f"save failed, will try again: {save_error}")
                        
                    forget_old_positions(seen_positions)
                    last_save_time = time.time()

            except Exception as unexpected_error:
                log_message(f"unexpected error, carrying on: {unexpected_error}")

            execution_time = time.time() - loop_start_time
            sleep_time = max(0, POLL_INTERVAL - execution_time)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print()
        log_message("stopping and saving remaining data...")
        try:
            save_positions_to_disk(position_buffer)
        except Exception as save_error:
            log_message(f"last save failed: {save_error}")

if __name__ == "__main__":
    run_collection_loop()