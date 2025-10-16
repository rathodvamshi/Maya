import asyncio
from app.services.task_service import create_user_task

async def main():
    task = await create_user_task(
        user_id='68ed00bab3333a2a39941f26',
        title='Email Reminder Test',
        task_time='in 3 minutes',
        payload={'note': 'user flow'},
        user_email='codehub369@gmail.com'
    )
    print("✅ Task created:", task)

asyncio.run(main())
