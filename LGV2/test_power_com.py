import threading
import time
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Power_6 import ProgrammablePowerSupply
from power_communication_manager import power_comm_manager

def test_station(station_id, duration=10):
    print(f"Starting test for Station {station_id} on COM4")
    try:
        psu = ProgrammablePowerSupply(port='COM4', station_address=station_id, station_idx=station_id)
        
        start_time = time.time()
        count = 0
        errors = 0
        
        while time.time() - start_time < duration:
            try:
                # Read status
                t0 = time.time()
                status = psu.read_status()
                t1 = time.time()
                
                if status:
                    # print(f"Station {station_id}: {status['voltage']:.2f}V, {status['current']:.2f}A (Time: {t1-t0:.3f}s)")
                    count += 1
                else:
                    print(f"Station {station_id}: Read Failed")
                    errors += 1
                
                # Small sleep to simulate workload, but small enough to cause contention
                time.sleep(0.01) 
                
            except Exception as e:
                print(f"Station {station_id} Error: {e}")
                errors += 1
                
        print(f"Station {station_id} Finished. Total Reads: {count}, Errors: {errors}")
        return count, errors
        
    except Exception as e:
        print(f"Station {station_id} Init Failed: {e}")
        return 0, 1

def main():
    print("Testing Simultaneous Access for Station 6 and 7 on COM4")
    print("Ensuring 5ms interval via PowerCommunicationManager")
    
    # Create threads
    t1 = threading.Thread(target=test_station, args=(6, 5)) # 5 seconds test
    t2 = threading.Thread(target=test_station, args=(7, 5))
    
    start_global = time.time()
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    end_global = time.time()
    print(f"Total Test Time: {end_global - start_global:.2f}s")
    print("Done.")

if __name__ == "__main__":
    main()
