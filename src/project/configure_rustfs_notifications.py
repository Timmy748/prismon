import asyncio

from project.storage import RustFSStorage


async def configure_notifications() -> None:
    storage = RustFSStorage()
    await storage.ensure_upload_notifications()


def main() -> None:
    asyncio.run(configure_notifications())


if __name__ == '__main__':
    main()
