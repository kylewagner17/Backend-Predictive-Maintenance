from pymodbus.client import ModbusTcpClient
from app.database import SessionLocal
from app import crud, schemas
import time

#change to the actual PLC IP address
PLC_IP = "127.0.0.1"
PLC_PORT = 5020
START_REGISTER = 0
REGISTER_COUNT = 4

def poll_plc():
    client = ModbusTcpClient(PLC_IP, port=PLC_PORT)
    client.connect()

    if not client.connect():
        print("PLC connection failed")
        return

    result = client.read_holding_registers(
        address=START_REGISTER,
        count=REGISTER_COUNT,
        device_id=0
    )

    print("Raw result:", result)
    print("Is error:", result.isError())

    if result.isError():
        print("Modbus read error")
        client.close()
        return


    registers = result.registers

    client.close()

    db = SessionLocal()

    try:
        for offset, value in enumerate(registers):
            register_address = START_REGISTER + offset

            mapping = crud.get_device_by_register(db, register_address)

            if mapping: 
                reading = schemas.SensorReadingCreate(
                    device_id=mapping.device_id,
                    reading=float(value),
                    status="OK"
                )
                crud.create_sensor_reading(db, reading)

        print("PLC values saved:", registers)

    except Exception as e:
        print("Database error:", e)

    finally:
        db.close()


def plc_loop():
    while True:
        try:
            poll_plc()
        except Exception as e:
            print("PLC loop crashed:", e)