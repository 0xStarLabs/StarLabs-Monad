from loguru import logger
import urllib3
import sys
import asyncio
import platform
import random
import traceback
from process import start

# Set Windows Event Loop Policy (if on Windows)
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def loop_task():
    """Continuously runs start() with a delay between runs."""
    while True:
        try:
            await start()  # Run your async function
        except Exception as e:
            logger.error(f"❌ Error occurred: {e}")
            traceback.print_exc()
        
        delay = random.randint(30, 60)  # Random delay between 30-60 seconds
        logger.info(f"🔄 Restarting in {delay} seconds...")
        await asyncio.sleep(delay)


async def main():
    configuration()
    await loop_task()  # Runs the loop forever


def configuration():
    """Setup logging and disable warnings."""
    urllib3.disable_warnings()
    logger.remove()
    logger.add(
        sys.stdout,
        colorize=True,
        format="<light-cyan>{time:HH:mm:ss}</light-cyan> | <level>{level: <8}</level> | <fg #ffffff>{name}:{line}</fg #ffffff> - <bold>{message}</bold>",
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Loop stopped by user.")
