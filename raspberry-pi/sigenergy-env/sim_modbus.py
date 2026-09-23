import asyncio
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusDeviceContext
from pymodbus.server import StartAsyncTcpServer

async def main():
    # Start address at 1 to prevent internal pymodbus 3.15 -1 conversion
    store = ModbusDeviceContext(
        hr=ModbusSequentialDataBlock(1, [100, 200, 300, 400])
    )
    
    # Handle version difference between 'devices' (v3.15+) and 'slaves'
    try:
        context = ModbusServerContext(devices=store, single=True)
    except TypeError:
        context = ModbusServerContext(slaves=store, single=True)

    print("--- Local Modbus TCP Simulator active on port 5020 ---")
    await StartAsyncTcpServer(context, address=("0.0.0.0", 5020))

if __name__ == "__main__":
    asyncio.run(main())
