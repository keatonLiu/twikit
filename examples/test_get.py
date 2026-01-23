import asyncio

import noble_tls

async def main():
    client = noble_tls.Session(
        client=noble_tls.Client.CHROME_131,
        random_tls_extension_order=True
    )
    client.proxies = {
        'http': 'http://data_crawler-zone-un2296609:data_crawler@9we0cb7cde4f38d.ipidea.online:2333',
        'https': 'http://data_crawler-zone-un2296609:data_crawler@9we0cb7cde4f38d.ipidea.online:2333'
    }
    client.headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    }
    response = await client.get('https://twitter.com/i/js_inst?c_name=ui_metrics')
    print(response.text)

if __name__ == '__main__':
    asyncio.run(main())
