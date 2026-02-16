from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusDeviceContext
from pymodbus.datastore import ModbusServerContext

# Create holding registers starting at address 0
data_block = ModbusSequentialDataBlock(0, [10, 20, 30, 40])

device_context = ModbusDeviceContext(hr=data_block)

context = ModbusServerContext(devices=device_context, single=True)

print("Starting Modbus test server on port 5020...")
StartTcpServer(context, address=("0.0.0.0", 5020))