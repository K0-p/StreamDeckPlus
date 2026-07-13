import asyncio
from datetime import datetime

class ClockHandler:

    def __init__(self, state):
        self.state = state
        self.state.hr24 = False
        self.running = True

    def run(self):
        asyncio.run(self._main())

    async def _main(self):
        await self._clock_loop()

    async def _clock_loop(self):
        while self.running:
            now = datetime.now()
            self.state.clock = {
                "hour": now.strftime("%H"),
                "minute": now.strftime("%M"),
                "text": now.strftime("%H . %M"),
            }
            self.state.render_queue.put("clock")
            # Wake exactly at the next minute
            await asyncio.sleep(60 - now.second)

    def stop(self):
        self.running = False