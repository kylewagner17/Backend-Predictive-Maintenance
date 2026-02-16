import time
from pymodbus.client import ModbusTcpClient

from app.config import settings
from app.database import SessionLocal
from app import crud, schemas


def poll_plc():
    client = ModbusTcpClient(settings.plc_host, port=settings.plc_port)

    if not client.connect():
        print("PLC connection failed")
        return

    result = client.read_holding_registers(
        address=settings.plc_start_register,
        count=settings.plc_register_count,
        device_id=settings.plc_device_id,
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
            register_address = settings.plc_start_register + offset

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
        time.sleep(settings.plc_poll_interval_seconds)