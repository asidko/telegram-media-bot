# Telegram media bot

`version: v1.0.0`

A Telegram bot integrating with the Jackett search engine to streamline torrent searches. It efficiently fetches and
presents a curated list of torrent results to users, complete with magnet links for easy access and download.

## Quick start

1. Run the Jackett server and note the API key. (see [linuxserver/jackett](https://docs.linuxserver.io/images/docker-jackett/#docker-compose-recommended-click-here-for-more-info) for detailed instructions)  
    Simple run example for demo purpose:
    ```bash
    docker run -d --name=myjackett -p 9117:9117 linuxserver/jackett
    ```
    - Then, go to `http://localhost:9117` and copy the API key.
    - After, press the `+ Add indexer` button and add some torrent providers to search for torrents, for example `1337x` and `The Pirate Bay`.
    - Jackett is now ready to use.
2. Create a new bot on Telegram and note the **bot token**. (use [@BotFather](https://t.me/BotFather) to do it)
3. Run this bot using the following command:

```bash
docker run -d --rm --name telegram-media-bot \
    -e JACKETT_API_KEY=your_jackett_api_key_here \
    -e JACKETT_URL=http://myjackett:9117 \
    -e BOT_TOKEN=your_telegram_bot_token_here \
    windranger/telegram-media-bot:latest
```

## Usage

Usage it pretty straightforward. Just start a chat with the bot and write a message to make the bot search for torrents.

<img width="1217" alt="image" src="https://github.com/asidko/asidko/assets/22843881/373de838-b502-4a10-ac02-0f681997702c">

Use the buttons to filter the results.

<img width="775" alt="image" src="https://github.com/asidko/asidko/assets/22843881/28e45c88-313d-44d5-9808-2b3ad1e8972d">

Choose a torrent from the list and click the `/select...` link to get your download.

<img width="750" alt="image" src="https://github.com/asidko/telegram-media-bot/assets/22843881/b1afa83a-9009-43ac-8f81-070a778d5d4d">

Press the button to download the torrent.

### Disclaimer

This project is intended for educational purposes only. The author does not condone the use of it for illegal activities.  




