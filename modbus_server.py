from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusDeviceContext
from pymodbus.datastore import ModbusServerContext

# ModbusDeviceContext uses 1-based addressing (adds 1 to client address).
# Client sends address=0 for "first register" → context asks store for address 1.
# So create the block starting at 1 so addresses 1–4 exist for read 0, count 4.
data_block = ModbusSequentialDataBlock(1, [10, 20, 30, 40])

device_context = ModbusDeviceContext(hr=data_block)

# single=True: one context for all unit IDs. Clients should use device_id=1
# (device_id=0 is often treated as broadcast and can cause Illegal Data Address on read).
context = ModbusServerContext(devices=device_context, single=True)

print("Starting Modbus test server on port 5020...")
StartTcpServer(context, address=("0.0.0.0", 5020))